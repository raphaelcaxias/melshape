"""
Melshape — Notification Repository.

Gerencia notificações in-app e lembretes recorrentes.

Princípios:
- Fila: notificações pendentes de entrega
- Histórico: notificações já entregues
- Lembretes: configurações recorrentes (check-in diário, etc.)
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Modelos: dataclasses imutáveis para todas as entidades
- Validação: dados são validados antes de salvar
- Logging: todas as operações são logadas

Arquitetura:
    NotificationRepository
    ├── get_pending_notifications(limit) -> list[Notification]
    ├── mark_as_delivered(notif_id) -> bool
    ├── create_notification(mensagem, tipo, agendada_para) -> Notification | None
    ├── delete_notification(notif_id) -> bool
    ├── get_reminders() -> list[RecurringReminder]
    ├── create_reminder(tipo, mensagem, horario, frequencia) -> RecurringReminder | None
    ├── update_reminder(reminder_id, data) -> bool
    ├── delete_reminder(reminder_id) -> bool
    ├── create_checkin_reminder() -> RecurringReminder | None
    └── get_notification_history(days) -> list[Notification]
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("Melshape.NotifRepo")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DE NOTIFICAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Notification:
    """
    Modelo de notificação in-app.
    
    Attributes:
        id: ID único da notificação
        user_id: ID do usuário
        mensagem: Mensagem da notificação
        tipo: Tipo da notificação (engajamento/streak_risco/meta_proxima/lembrete/boas_vindas)
        enviada: Se a notificação foi entregue
        agendada_para: Data/hora agendada (se aplicável)
        enviada_em: Timestamp de entrega (se enviada)
        criado_em: Timestamp de criação
    """
    id: str
    user_id: str
    mensagem: str
    tipo: str = "engajamento"
    enviada: bool = False
    agendada_para: str | None = None
    enviada_em: str | None = None
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Notification:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            mensagem=data.get("mensagem", ""),
            tipo=data.get("tipo", "engajamento"),
            enviada=data.get("enviada", False),
            agendada_para=data.get("agendada_para"),
            enviada_em=data.get("enviada_em"),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )
    
    @property
    def is_pending(self) -> bool:
        """Verifica se a notificação está pendente."""
        return not self.enviada
    
    @property
    def tipo_label(self) -> str:
        """Retorna o rótulo do tipo de notificação."""
        labels = {
            "engajamento": "📢 Engajamento",
            "streak_risco": "🔥 Streak em Risco",
            "meta_proxima": "🎯 Meta Próxima",
            "lembrete": "⏰ Lembrete",
            "boas_vindas": "👋 Boas-vindas",
            "conquista": "🏆 Conquista",
        }
        return labels.get(self.tipo, self.tipo)


@dataclass(frozen=True)
class RecurringReminder:
    """
    Modelo de lembrete recorrente.
    
    Attributes:
        id: ID único do lembrete
        user_id: ID do usuário
        tipo: Tipo do lembrete (checkin_diario/hidratacao/treino/etc)
        mensagem: Mensagem do lembrete
        horario: Horário do lembrete (HH:MM)
        frequencia: Frequência (daily/weekly)
        ativo: Se o lembrete está ativo
        dias_semana: Dias da semana (para frequência weekly)
        criado_em: Timestamp de criação
    """
    id: str
    user_id: str
    tipo: str
    mensagem: str
    horario: str = "08:00"
    frequencia: str = "daily"
    ativo: bool = True
    dias_semana: list[int] | None = None
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecurringReminder:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            tipo=data.get("tipo", ""),
            mensagem=data.get("mensagem", ""),
            horario=data.get("horario", "08:00"),
            frequencia=data.get("frequencia", "daily"),
            ativo=data.get("ativo", True),
            dias_semana=data.get("dias_semana"),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )
    
    @property
    def tipo_label(self) -> str:
        """Retorna o rótulo do tipo de lembrete."""
        labels = {
            "checkin_diario": "✅ Check-in Diário",
            "hidratacao": "💧 Hidratação",
            "treino": "🏋️ Treino",
            "refeicao": "🍽️ Refeição",
            "pesagem": "⚖️ Pesagem",
        }
        return labels.get(self.tipo, self.tipo)
    
    @property
    def frequencia_label(self) -> str:
        """Retorna o rótulo da frequência."""
        labels = {
            "daily": "Diário",
            "weekly": "Semanal",
            "custom": "Personalizado",
        }
        return labels.get(self.frequencia, self.frequencia)


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATION REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────

class NotificationRepository:
    """
    Mixin para gerenciamento de notificações.
    
    Requer que a classe base tenha:
        - self.client (Supabase client)
        - self.is_real (bool)
        - self.uid() -> str
        - self.mock (dict)
    
    Example:
        >>> class Database(NotificationRepository):
        ...     def __init__(self):
        ...         self.client = None
        ...         self.is_real = False
        ...         self.mock = {"fila_notificacoes": {}}
        ...     
        ...     def uid(self) -> str:
        ...         return "user@example.com"
        
        >>> db = Database()
        >>> notif = db.create_notification("Bem-vindo ao Melshape!", "boas_vindas")
        >>> if notif:
        ...     print(f"Notificação criada: {notif.id}")
    """

    # ─────────────────────────────────────────────────────────────────────────
    # FILA DE NOTIFICAÇÕES
    # ─────────────────────────────────────────────────────────────────────────

    def get_pending_notifications(self, limit: int = 5) -> list[Notification]:
        """
        Retorna notificações pendentes não entregues.
        
        Args:
            limit: Número máximo de notificações
            
        Returns:
            Lista de objetos Notification (ordenados por data descendente)
            
        Example:
            >>> pending = db.get_pending_notifications(limit=3)
            >>> for n in pending:
            ...     print(f"{n.tipo_label}: {n.mensagem}")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("fila_notificacoes")
                    .select("*")
                    .eq("perfil_id", uid)
                    .eq("enviada", False)
                    .order("criado_em", desc=True)
                    .limit(limit)
                    .execute()
                )
                
                return [self._build_notification_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_pending_notifications Supabase: {e}")
        
        # Fallback MockDB
        key = f"notif_fila_{uid}"
        pending_data = [
            n for n in self.mock.get(key, [])
            if not n.get("enviada", False)
        ]
        
        # Ordena por criado_em descendente
        sorted_pending = sorted(
            pending_data,
            key=lambda x: x.get("criado_em", ""),
            reverse=True
        )
        
        return [self._build_notification_from_data(row) for row in sorted_pending[:limit]]

    def mark_as_delivered(self, notif_id: str) -> bool:
        """
        Marca uma notificação como entregue.

        Args:
            notif_id: ID da notificação

        Returns:
            True se marcada com sucesso, False caso contrário

        Example:
            >>> success = db.mark_as_delivered(notif_id)
            >>> if success:
            ...     print("Notificação marcada como entregue!")
        """
        if not notif_id:
            logger.warning("❌ notif_id é obrigatório")
            return False

        if self.is_real and self.client:
            try:
                self.client.table("fila_notificacoes").update({
                    "enviada": True,
                    "enviada_em": datetime.now(timezone.utc).isoformat(),
                }).eq("id", notif_id).execute()

                logger.info(f"✅ Notificação marcada como entregue no Supabase: {notif_id}")
                return True

            except Exception as e:
                logger.error(f"mark_as_delivered Supabase: {e}")

        # Fallback MockDB
        uid = self.uid()
        key = f"notif_fila_{uid}"
        notifications = self.mock.get(key, [])

        for notif in notifications:
            if notif.get("id") == notif_id:
                notif["enviada"] = True
                notif["enviada_em"] = datetime.now(timezone.utc).isoformat()
                logger.info(f"✅ Notificação marcada como entregue no MockDB: {notif_id}")
                return True
        
        logger.warning(f"❌ Notificação não encontrada: {notif_id}")
        return False

    def mark_all_delivered(self, notif_ids: list[str]) -> int:
        """
        Sprint 5 — Batch update: marca múltiplas notificações como entregues
        em uma única query Supabase (.in_()) ao invés de N queries individuais.

        Args:
            notif_ids: Lista de IDs a marcar.

        Returns:
            Número de notificações marcadas.
        """
        if not notif_ids:
            return 0

        if self.is_real and self.client:
            try:
                self.client.table("fila_notificacoes").update({
                    "enviada": True,
                    "enviada_em": datetime.now(timezone.utc).isoformat(),
                }).in_("id", notif_ids).execute()
                logger.info(f"✅ {len(notif_ids)} notificações marcadas em batch")
                return len(notif_ids)
            except Exception as e:
                logger.error(f"mark_all_delivered: {e}")
                # Fallback: individual
                count = 0
                for nid in notif_ids:
                    if self.mark_as_delivered(nid):
                        count += 1
                return count

        # MockDB fallback
        for nid in notif_ids:
            self.mark_as_delivered(nid)
        return len(notif_ids)

    def create_notification(
        self,
        mensagem: str,
        tipo: str = "engajamento",
        agendada_para: str | None = None,
    ) -> Notification | None:
        """
        Cria uma nova notificação na fila.
        
        Args:
            mensagem: Mensagem da notificação
            tipo: Tipo da notificação (engajamento/streak_risco/meta_proxima/lembrete/boas_vindas)
            agendada_para: Data/hora agendada (ISO format)
            
        Returns:
            Objeto Notification criado ou None se falhar
            
        Example:
            >>> notif = db.create_notification("Check-in pendente!", "lembrete")
            >>> if notif:
            ...     print(f"Notificação criada: {notif.id}")
        """
        uid = self.uid()
        
        # Validações
        if not mensagem or not mensagem.strip():
            logger.warning("❌ Mensagem é obrigatória")
            return None
        
        valid_tipos = {"engajamento", "streak_risco", "meta_proxima", "lembrete", "boas_vindas", "conquista"}
        if tipo not in valid_tipos:
            logger.warning(f"❌ Tipo de notificação inválido: {tipo}")
            return None
        
        notif_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                payload = {
                    "id": notif_id,
                    "perfil_id": uid,
                    "mensagem": mensagem,
                    "tipo": tipo,
                    "enviada": False,
                    "criado_em": datetime.now(timezone.utc).isoformat(),
                }
                if agendada_para:
                    payload["agendada_para"] = agendada_para
                
                self.client.table("fila_notificacoes").insert(payload).execute()
                
                notification = self._build_notification_from_data(payload)
                logger.info(f"✅ Notificação criada no Supabase: {tipo}")
                return notification
                
            except Exception as e:
                logger.error(f"create_notification Supabase: {e}")
        
        # Fallback MockDB
        key = f"notif_fila_{uid}"
        notif_data = {
            "id": notif_id,
            "user_id": uid,
            "mensagem": mensagem,
            "tipo": tipo,
            "enviada": False,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
        
        if agendada_para:
            notif_data["agendada_para"] = agendada_para
        
        self.mock.setdefault(key, []).append(notif_data)
        
        notification = self._build_notification_from_data(notif_data)
        logger.info(f"✅ Notificação criada no MockDB: {tipo}")
        return notification

    def delete_notification(self, notif_id: str) -> bool:
        """
        Remove uma notificação da fila.
        
        Args:
            notif_id: ID da notificação
            
        Returns:
            True se removida com sucesso, False caso contrário
            
        Example:
            >>> success = db.delete_notification(notif_id)
            >>> if success:
            ...     print("Notificação removida!")
        """
        if not notif_id:
            logger.warning("❌ notif_id é obrigatório")
            return False
        
        if self.is_real and self.client:
            try:
                self.client.table("fila_notificacoes").delete().eq("id", notif_id).execute()
                logger.info(f"✅ Notificação removida no Supabase: {notif_id}")
                return True
                
            except Exception as e:
                logger.error(f"delete_notification Supabase: {e}")
        
        # Fallback MockDB
        uid = self.uid()
        key = f"notif_fila_{uid}"
        notifications = self.mock.get(key, [])
        
        for i, notif in enumerate(notifications):
            if notif.get("id") == notif_id:
                notifications.pop(i)
                logger.info(f"✅ Notificação removida no MockDB: {notif_id}")
                return True
        
        logger.warning(f"❌ Notificação não encontrada: {notif_id}")
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # LEMBRETES RECORRENTES
    # ─────────────────────────────────────────────────────────────────────────

    def get_reminders(self) -> list[RecurringReminder]:
        """
        Retorna lembretes recorrentes do paciente.
        
        Returns:
            Lista de objetos RecurringReminder
            
        Example:
            >>> reminders = db.get_reminders()
            >>> for r in reminders:
            ...     print(f"{r.tipo_label} - {r.horario} ({r.frequencia_label})")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("lembretes_recorrentes")
                    .select("*")
                    .eq("perfil_id", uid)
                    .eq("ativo", True)
                    .execute()
                )
                
                return [self._build_reminder_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_reminders Supabase: {e}")
        
        # Fallback MockDB
        key = f"lembretes_{uid}"
        reminders_data = [
            r for r in self.mock.get(key, [])
            if r.get("ativo", True)
        ]
        
        return [self._build_reminder_from_data(row) for row in reminders_data]

    def create_reminder(
        self,
        tipo: str,
        mensagem: str,
        horario: str = "08:00",
        frequencia: str = "daily",
        dias_semana: list[int] | None = None,
    ) -> RecurringReminder | None:
        """
        Cria um novo lembrete recorrente.
        
        Args:
            tipo: Tipo do lembrete (checkin_diario/hidratacao/treino/etc)
            mensagem: Mensagem do lembrete
            horario: Horário do lembrete (HH:MM)
            frequencia: Frequência (daily/weekly)
            dias_semana: Dias da semana (0=domingo, 6=sábado) - apenas para weekly
            
        Returns:
            Objeto RecurringReminder criado ou None se falhar
            
        Example:
            >>> reminder = db.create_reminder("hidratacao", "💧 Hora de beber água!", "10:00")
            >>> if reminder:
            ...     print(f"Lembrete criado: {reminder.id}")
        """
        uid = self.uid()
        
        # Validações
        if not tipo or not tipo.strip():
            logger.warning("❌ Tipo é obrigatório")
            return None
        
        if not mensagem or not mensagem.strip():
            logger.warning("❌ Mensagem é obrigatória")
            return None
        
        # Valida formato do horário
        if ":" not in horario:
            logger.warning(f"❌ Horário inválido: {horario} (use HH:MM)")
            return None
        
        valid_frequencias = {"daily", "weekly"}
        if frequencia not in valid_frequencias:
            logger.warning(f"❌ Frequência inválida: {frequencia}")
            return None
        
        reminder_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                payload = {
                    "id": reminder_id,
                    "perfil_id": uid,
                    "tipo": tipo,
                    "mensagem": mensagem,
                    "horario": horario,
                    "frequencia": frequencia,
                    "ativo": True,
                }
                
                if frequencia == "weekly" and dias_semana:
                    payload["dias_semana"] = dias_semana
                
                self.client.table("lembretes_recorrentes").insert(payload).execute()
                
                reminder = self._build_reminder_from_data(payload)
                logger.info(f"✅ Lembrete criado no Supabase: {tipo}")
                return reminder
                
            except Exception as e:
                logger.error(f"create_reminder Supabase: {e}")
        
        # Fallback MockDB
        key = f"lembretes_{uid}"
        reminder_data = {
            "id": reminder_id,
            "user_id": uid,
            "tipo": tipo,
            "mensagem": mensagem,
            "horario": horario,
            "frequencia": frequencia,
            "ativo": True,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
        
        if frequencia == "weekly" and dias_semana:
            reminder_data["dias_semana"] = dias_semana
        
        self.mock.setdefault(key, []).append(reminder_data)
        
        reminder = self._build_reminder_from_data(reminder_data)
        logger.info(f"✅ Lembrete criado no MockDB: {tipo}")
        return reminder

    def update_reminder(self, reminder_id: str, data: dict[str, Any]) -> bool:
        """
        Atualiza um lembrete recorrente.
        
        Args:
            reminder_id: ID do lembrete
            data: Dicionário com campos a atualizar
            
        Returns:
            True se atualizado com sucesso, False caso contrário
            
        Example:
            >>> success = db.update_reminder(reminder_id, {"horario": "09:00", "ativo": False})
            >>> if success:
            ...     print("Lembrete atualizado!")
        """
        if not reminder_id:
            logger.warning("❌ reminder_id é obrigatório")
            return False
        
        if self.is_real and self.client:
            try:
                self.client.table("lembretes_recorrentes").update(data).eq("id", reminder_id).execute()
                logger.info(f"✅ Lembrete atualizado no Supabase: {reminder_id}")
                return True
                
            except Exception as e:
                logger.error(f"update_reminder Supabase: {e}")
        
        # Fallback MockDB
        uid = self.uid()
        key = f"lembretes_{uid}"
        reminders = self.mock.get(key, [])
        
        for reminder in reminders:
            if reminder.get("id") == reminder_id:
                reminder.update(data)
                logger.info(f"✅ Lembrete atualizado no MockDB: {reminder_id}")
                return True
        
        logger.warning(f"❌ Lembrete não encontrado: {reminder_id}")
        return False

    def delete_reminder(self, reminder_id: str) -> bool:
        """
        Remove um lembrete recorrente.
        
        Args:
            reminder_id: ID do lembrete
            
        Returns:
            True se removido com sucesso, False caso contrário
            
        Example:
            >>> success = db.delete_reminder(reminder_id)
            >>> if success:
            ...     print("Lembrete removido!")
        """
        if not reminder_id:
            logger.warning("❌ reminder_id é obrigatório")
            return False
        
        if self.is_real and self.client:
            try:
                self.client.table("lembretes_recorrentes").delete().eq("id", reminder_id).execute()
                logger.info(f"✅ Lembrete removido no Supabase: {reminder_id}")
                return True
                
            except Exception as e:
                logger.error(f"delete_reminder Supabase: {e}")
        
        # Fallback MockDB
        uid = self.uid()
        key = f"lembretes_{uid}"
        reminders = self.mock.get(key, [])
        
        for i, reminder in enumerate(reminders):
            if reminder.get("id") == reminder_id:
                reminders.pop(i)
                logger.info(f"✅ Lembrete removido no MockDB: {reminder_id}")
                return True
        
        logger.warning(f"❌ Lembrete não encontrado: {reminder_id}")
        return False

    def create_checkin_reminder(self) -> RecurringReminder | None:
        """
        Cria um lembrete recorrente de check-in diário.
        
        Returns:
            Objeto RecurringReminder criado ou None se já existir
            
        Example:
            >>> reminder = db.create_checkin_reminder()
            >>> if reminder:
            ...     print(f"Lembrete de check-in criado: {reminder.id}")
            ... else:
            ...     print("Lembrete de check-in já existe")
        """
        # Verifica se já existe
        reminders = self.get_reminders()
        if any(r.tipo == "checkin_diario" for r in reminders):
            logger.debug("Lembrete de check-in já existe")
            return None
        
        return self.create_reminder(
            tipo="checkin_diario",
            mensagem="✅ Seu check-in de hoje está esperando. 30 segundos.",
            horario="08:00",
            frequencia="daily",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # HISTÓRICO
    # ─────────────────────────────────────────────────────────────────────────

    def get_notification_history(self, days: int = 7) -> list[Notification]:
        """
        Retorna histórico de notificações entregues.
        
        Args:
            days: Número de dias
            
        Returns:
            Lista de objetos Notification (ordenados por data descendente)
            
        Example:
            >>> history = db.get_notification_history(days=7)
            >>> for n in history:
            ...     print(f"{n.criado_em}: {n.mensagem}")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                from datetime import timedelta
                
                cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
                
                response = (
                    self.client.table("historico_notificacoes")
                    .select("*")
                    .eq("perfil_id", uid)
                    .gte("criado_em", cutoff)
                    .order("criado_em", desc=True)
                    .limit(50)
                    .execute()
                )
                
                return [self._build_notification_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_notification_history Supabase: {e}")
        
        # Fallback MockDB
        # No MockDB, usamos as notificações marcadas como entregues
        key = f"notif_fila_{uid}"
        history_data = [
            n for n in self.mock.get(key, [])
            if n.get("enviada", False)
        ]
        
        # Ordena por enviado_em descendente
        sorted_history = sorted(
            history_data,
            key=lambda x: x.get("enviada_em", x.get("criado_em", "")),
            reverse=True
        )
        
        return [self._build_notification_from_data(row) for row in sorted_history[:50]]

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS DE CONVERSÃO
    # ─────────────────────────────────────────────────────────────────────────

    def _build_notification_from_data(self, data: dict[str, Any]) -> Notification:
        """Converte um dicionário para um objeto Notification."""
        return Notification.from_dict(data)

    def _build_reminder_from_data(self, data: dict[str, Any]) -> RecurringReminder:
        """Converte um dicionário para um objeto RecurringReminder."""
        return RecurringReminder.from_dict(data)


__all__ = [
    "NotificationRepository",
    "Notification",
    "RecurringReminder",
]
