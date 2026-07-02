"""
Melshape — Habit Repository.

Gerencia hábitos do paciente: criação, registro diário, streak e aderência.

Princípios:
- Hábito: uma ação recorrente que o paciente quer incorporar
- Registro: marcação diária de conclusão do hábito
- Streak: dias consecutivos de conclusão
- Aderência: % de dias concluídos em um período
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Modelos: dataclasses imutáveis para todas as entidades
- Validação: dados são validados antes de salvar
- Logging: todas as operações são logadas

Arquitetura:
    HabitRepository
    ├── get_habits() -> list[Habit]
    ├── create_habit(nome, categoria, icone, frequencia) -> Habit | None
    ├── archive_habit(habit_id) -> bool
    ├── delete_habit(habit_id) -> bool
    ├── register_habit(habit_id, data_str, observacao) -> bool
    ├── get_habit_records(habit_id, days) -> list[HabitRecord]
    ├── get_today_records() -> set[str]
    ├── get_streak(habit_id) -> int
    └── get_adherence(habit_id, days) -> float
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("Melshape.HabitRepo")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DE HÁBITOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Habit:
    """
    Modelo de hábito do paciente.
    
    Attributes:
        id: ID único do hábito
        user_id: ID do usuário
        nome: Nome do hábito
        descricao: Descrição do hábito
        categoria: Categoria (hidratacao/nutricao/movimento/sono/mental/geral)
        icone: Emoji do hábito
        frequencia: Frequência (daily/weekly)
        ativo: Se o hábito está ativo
        criado_em: Timestamp de criação
    """
    id: str
    user_id: str
    nome: str
    descricao: str = ""
    categoria: str = "geral"
    icone: str = "⭐"
    frequencia: str = "daily"
    ativo: bool = True
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Habit:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            nome=data.get("nome", ""),
            descricao=data.get("descricao", ""),
            categoria=data.get("categoria", "geral"),
            icone=data.get("icone", "⭐"),
            frequencia=data.get("frequencia", "daily"),
            ativo=data.get("ativo", True),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )


@dataclass(frozen=True)
class HabitRecord:
    """
    Modelo de registro de hábito.
    
    Attributes:
        id: ID único do registro
        habit_id: ID do hábito
        user_id: ID do usuário
        data_registro: Data do registro (YYYY-MM-DD)
        concluido: Se o hábito foi concluído
        observacao: Observação opcional
        criado_em: Timestamp de criação
    """
    id: str
    habit_id: str
    user_id: str
    data_registro: str
    concluido: bool = True
    observacao: str = ""
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HabitRecord:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            habit_id=data.get("habito_id", data.get("habit_id", "")),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            data_registro=data.get("data_registro", ""),
            concluido=data.get("concluido", True),
            observacao=data.get("observacao", ""),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )


# ─────────────────────────────────────────────────────────────────────────────
# HABIT REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────

class HabitRepository:
    """
    Mixin para gerenciamento de hábitos.
    
    Requer que a classe base tenha:
        - self.client (Supabase client)
        - self.is_real (bool)
        - self.uid() -> str
        - self.mock (dict)
    
    Example:
        >>> class Database(HabitRepository):
        ...     def __init__(self):
        ...         self.client = None
        ...         self.is_real = False
        ...         self.mock = {"habitos": []}
        ...     
        ...     def uid(self) -> str:
        ...         return "user@example.com"
        
        >>> db = Database()
        >>> habit = db.create_habit("Beber 2L de água", "hidratacao", "💧", "daily")
        >>> if habit:
        ...     print(f"Hábito criado: {habit.id}")
    """

    # ─────────────────────────────────────────────────────────────────────────
    # HÁBITOS
    # ─────────────────────────────────────────────────────────────────────────

    def get_habits(self) -> list[Habit]:
        """
        Retorna todos os hábitos ativos do paciente.
        
        Returns:
            Lista de objetos Habit
            
        Example:
            >>> habits = db.get_habits()
            >>> for habit in habits:
            ...     print(f"{habit.icone} {habit.nome}")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("habitos")
                    .select("*")
                    .eq("perfil_id", uid)
                    .eq("ativo", True)
                    .order("criado_em")
                    .execute()
                )
                
                return [self._build_habit_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_habits Supabase: {e}")
        
        # Fallback MockDB
        habits_data = [
            h for h in self.mock.get("habitos", [])
            if h.get("user_id") == uid and h.get("ativo", True)
        ]
        
        return [self._build_habit_from_data(row) for row in habits_data]

    def create_habit(
        self,
        nome: str,
        categoria: str = "geral",
        icone: str = "⭐",
        frequencia: str = "daily",
        descricao: str = "",
    ) -> Habit | None:
        """
        Cria um novo hábito para o paciente.
        
        Args:
            nome: Nome do hábito
            categoria: Categoria (hidratacao/nutricao/movimento/sono/mental/geral)
            icone: Emoji do hábito
            frequencia: daily ou weekly
            descricao: Descrição do hábito
            
        Returns:
            Objeto Habit criado ou None se falhar
            
        Example:
            >>> habit = db.create_habit("Beber 2L de água", "hidratacao", "💧", "daily")
            >>> if habit:
            ...     print(f"Hábito criado: {habit.id}")
            ... else:
            ...     print("Falha ao criar hábito")
        """
        uid = self.uid()
        
        # Validações
        if not nome or not nome.strip():
            logger.warning("❌ Nome do hábito é obrigatório")
            return None
        
        valid_categorias = {"hidratacao", "nutricao", "movimento", "sono", "mental", "geral"}
        if categoria not in valid_categorias:
            logger.warning(f"❌ Categoria inválida: {categoria}")
            return None
        
        valid_frequencias = {"daily", "weekly"}
        if frequencia not in valid_frequencias:
            logger.warning(f"❌ Frequência inválida: {frequencia}")
            return None
        
        habit_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                response = self.client.table("habitos").insert({
                    "id": habit_id,
                    "perfil_id": uid,
                    "nome": nome,
                    "descricao": descricao or None,
                    "categoria": categoria,
                    "icone": icone,
                    "frequencia": frequencia,
                    "ativo": True,
                }).execute()
                
                if response.data:
                    habit = self._build_habit_from_data(response.data[0])
                    logger.info(f"✅ Hábito criado no Supabase: {nome}")
                    return habit
                
            except Exception as e:
                logger.error(f"create_habit Supabase: {e}")
        
        # Fallback MockDB
        habit_data = {
            "id": habit_id,
            "user_id": uid,
            "nome": nome,
            "descricao": descricao,
            "categoria": categoria,
            "icone": icone,
            "frequencia": frequencia,
            "ativo": True,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
        
        self.mock.setdefault("habitos", []).append(habit_data)
        
        habit = self._build_habit_from_data(habit_data)
        logger.info(f"✅ Hábito criado no MockDB: {nome}")
        return habit

    def archive_habit(self, habit_id: str) -> bool:
        """
        Arquiva um hábito (desativa).
        
        Args:
            habit_id: ID do hábito
            
        Returns:
            True se arquivado com sucesso, False caso contrário
            
        Example:
            >>> success = db.archive_habit(habit_id)
            >>> if success:
            ...     print("Hábito arquivado!")
        """
        if not habit_id:
            logger.warning("❌ habit_id é obrigatório")
            return False
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("habitos")
                    .update({"ativo": False})
                    .eq("id", habit_id)
                    .execute()
                )
                
                if response.data:
                    logger.info(f"✅ Hábito arquivado no Supabase: {habit_id}")
                    return True
                
            except Exception as e:
                logger.error(f"archive_habit Supabase: {e}")
        
        # Fallback MockDB
        habits = self.mock.get("habitos", [])
        for habit in habits:
            if habit.get("id") == habit_id:
                habit["ativo"] = False
                logger.info(f"✅ Hábito arquivado no MockDB: {habit_id}")
                return True
        
        logger.warning(f"❌ Hábito não encontrado: {habit_id}")
        return False

    def delete_habit(self, habit_id: str) -> bool:
        """
        Remove permanentemente um hábito e seus registros.
        
        Args:
            habit_id: ID do hábito
            
        Returns:
            True se removido com sucesso, False caso contrário
            
        Example:
            >>> success = db.delete_habit(habit_id)
            >>> if success:
            ...     print("Hábito removido!")
        """
        if not habit_id:
            logger.warning("❌ habit_id é obrigatório")
            return False
        
        if self.is_real and self.client:
            try:
                # Remove registros primeiro
                self.client.table("registros_habitos").delete().eq("habito_id", habit_id).execute()
                
                # Remove o hábito
                response = self.client.table("habitos").delete().eq("id", habit_id).execute()
                
                if response.data:
                    logger.info(f"✅ Hábito removido no Supabase: {habit_id}")
                    return True
                
            except Exception as e:
                logger.error(f"delete_habit Supabase: {e}")
        
        # Fallback MockDB
        habits = self.mock.get("habitos", [])
        habit_found = False
        
        for i, habit in enumerate(habits):
            if habit.get("id") == habit_id:
                habits.pop(i)
                habit_found = True
                break
        
        # Remove registros
        key = f"reg_{habit_id}"
        if key in self.mock:
            del self.mock[key]
        
        if habit_found:
            logger.info(f"✅ Hábito removido no MockDB: {habit_id}")
            return True
        
        logger.warning(f"❌ Hábito não encontrado: {habit_id}")
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # REGISTROS
    # ─────────────────────────────────────────────────────────────────────────

    def register_habit(
        self,
        habit_id: str,
        data_str: str | None = None,
        observacao: str = "",
    ) -> bool:
        """
        Registra a conclusão de um hábito em uma data.
        
        Args:
            habit_id: ID do hábito
            data_str: Data no formato YYYY-MM-DD (padrão: hoje)
            observacao: Observação opcional
            
        Returns:
            True se registrado com sucesso, False caso contrário
            
        Example:
            >>> success = db.register_habit(habit_id)
            >>> if success:
            ...     print("Hábito registrado!")
        """
        uid = self.uid()
        data_str = data_str or date.today().isoformat()
        
        # Validações
        if not habit_id:
            logger.warning("❌ habit_id é obrigatório")
            return False
        
        # Verifica se o hábito existe e está ativo
        habits = self.get_habits()
        habit_exists = any(h.id == habit_id and h.ativo for h in habits)
        
        if not habit_exists:
            logger.warning(f"❌ Hábito não encontrado ou inativo: {habit_id}")
            return False
        
        record_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                self.client.table("registros_habitos").upsert({
                    "id": record_id,
                    "habito_id": habit_id,
                    "perfil_id": uid,
                    "data_registro": data_str,
                    "concluido": True,
                    "observacao": observacao or None,
                }, on_conflict="habito_id,data_registro").execute()
                
                logger.info(f"✅ Hábito registrado no Supabase: {habit_id} em {data_str}")
                return True
                
            except Exception as e:
                logger.error(f"register_habit Supabase: {e}")
        
        # Fallback MockDB
        key = f"reg_{habit_id}"
        records = self.mock.setdefault(key, [])
        
        # Verifica se já existe registro para esta data
        existing = next((r for r in records if r.get("data_registro") == data_str), None)
        
        if existing:
            # Atualiza registro existente
            existing["concluido"] = True
            existing["observacao"] = observacao
            logger.info(f"✅ Hábito atualizado no MockDB: {habit_id} em {data_str}")
        else:
            # Cria novo registro
            records.append({
                "id": record_id,
                "habito_id": habit_id,
                "user_id": uid,
                "data_registro": data_str,
                "concluido": True,
                "observacao": observacao,
                "criado_em": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(f"✅ Hábito registrado no MockDB: {habit_id} em {data_str}")
        
        return True

    def get_habit_records(self, habit_id: str, days: int = 30) -> list[HabitRecord]:
        """
        Retorna os registros de um hábito nos últimos N dias.
        
        Args:
            habit_id: ID do hábito
            days: Número de dias
            
        Returns:
            Lista de objetos HabitRecord (ordenados por data descendente)
            
        Example:
            >>> records = db.get_habit_records(habit_id, days=7)
            >>> for record in records:
            ...     print(f"{record.data_registro}: {record.concluido}")
        """
        uid = self.uid()
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("registros_habitos")
                    .select("*")
                    .eq("habito_id", habit_id)
                    .eq("perfil_id", uid)
                    .eq("concluido", True)
                    .gte("data_registro", cutoff)
                    .order("data_registro", desc=True)
                    .execute()
                )
                
                return [self._build_record_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_habit_records Supabase: {e}")
        
        # Fallback MockDB
        key = f"reg_{habit_id}"
        records_data = [
            r for r in self.mock.get(key, [])
            if r.get("data_registro", "") >= cutoff and r.get("concluido", False)
        ]
        
        # Ordena por data descendente
        sorted_records = sorted(
            records_data,
            key=lambda x: x.get("data_registro", ""),
            reverse=True
        )
        
        return [self._build_record_from_data(row) for row in sorted_records]

    def get_today_records(self) -> set[str]:
        """
        Retorna os IDs dos hábitos concluídos hoje.
        
        Returns:
            Set com IDs dos hábitos concluídos hoje
            
        Example:
            >>> done = db.get_today_records()
            >>> if habit_id in done:
            ...     print("Hábito já concluído hoje!")
        """
        uid = self.uid()
        today = date.today().isoformat()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("registros_habitos")
                    .select("habito_id")
                    .eq("perfil_id", uid)
                    .eq("data_registro", today)
                    .eq("concluido", True)
                    .execute()
                )
                
                return {x["habito_id"] for x in (response.data or [])}
                
            except Exception as e:
                logger.error(f"get_today_records Supabase: {e}")
        
        # Fallback MockDB
        done = set()
        
        for habit in self.get_habits():
            key = f"reg_{habit.id}"
            records = self.mock.get(key, [])
            
            if any(r.get("data_registro") == today and r.get("concluido") for r in records):
                done.add(habit.id)
        
        return done

    # ─────────────────────────────────────────────────────────────────────────
    # STREAK E ADERÊNCIA
    # ─────────────────────────────────────────────────────────────────────────

    def get_streak(self, habit_id: str) -> int:
        """
        Calcula a sequência atual de dias consecutivos do hábito.
        
        Args:
            habit_id: ID do hábito
            
        Returns:
            Número de dias consecutivos
            
        Example:
            >>> streak = db.get_streak(habit_id)
            >>> print(f"Sequência: {streak} dias")
        """
        records = self.get_habit_records(habit_id, days=365)
        
        if not records:
            return 0
        
        # Extrai datas únicas e ordena descendente
        dates = sorted(
            set(r.data_registro for r in records),
            reverse=True
        )
        
        streak = 0
        check_date = date.today()
        
        for date_str in dates:
            try:
                record_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                continue
            
            if record_date == check_date:
                streak += 1
                check_date -= timedelta(days=1)
            elif record_date < check_date:
                break
        
        return streak

    def get_adherence(self, habit_id: str, days: int = 30) -> float:
        """
        Calcula a taxa de aderência do hábito nos últimos N dias.
        
        Args:
            habit_id: ID do hábito
            days: Número de dias
            
        Returns:
            Taxa de aderência (0.0 a 1.0)
            
        Example:
            >>> adherence = db.get_adherence(habit_id, days=30)
            >>> print(f"Aderência: {adherence * 100:.1f}%")
        """
        if days <= 0:
            return 0.0
        
        records = self.get_habit_records(habit_id, days=days)
        
        # Conta dias únicos com registro
        unique_days = len(set(r.data_registro for r in records))
        
        # Calcula taxa de aderência
        adherence = unique_days / days
        
        return min(1.0, adherence)  # Limita a 1.0

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS DE CONVERSÃO
    # ─────────────────────────────────────────────────────────────────────────

    def _build_habit_from_data(self, data: dict[str, Any]) -> Habit:
        """Converte um dicionário para um objeto Habit."""
        return Habit.from_dict(data)

    def _build_record_from_data(self, data: dict[str, Any]) -> HabitRecord:
        """Converte um dicionário para um objeto HabitRecord."""
        return HabitRecord.from_dict(data)


__all__ = [
    "HabitRepository",
    "Habit",
    "HabitRecord",
]
