"""
Melshape — Database Professional Auth Mixin.

Gerencia autenticação e criação de profissionais de saúde.
Em produção, deve usar Supabase Auth. Em desenvolvimento, usa MockDB.

Princípios:
- Autenticação via email e senha
- Criação de profissionais com especialidade e registro (CRN/CRM)
- Fallback automático: Supabase → MockDB
- Hash de senha com PBKDF2 (via security.py)
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de salvar
- Logging: todas as operações são logadas

Arquitetura:
    ProfessionalAuthMixin
    ├── get_professional(email, password) -> Professional | None
    ├── create_professional(email, password, name, specialty, crn) -> Professional | None
    ├── get_professional_by_email(email) -> Professional | None
    ├── update_professional(email, data) -> bool
    ├── delete_professional(email) -> bool
    └── _build_professional_from_data(data) -> Professional (helper)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import config
from core.models import Plan, Professional, Specialty
from core.security import hash_password, validate_email, validate_password, verify_password

logger = logging.getLogger("Melshape.Database.ProAuth")


class ProfessionalAuthMixin:
    """
    Mixin para autenticação e criação de profissionais.
    
    Requer que a classe base tenha:
        - self.client (Supabase client)
        - self.is_real (bool)
        - self.mock (dict)
    
    Example:
        >>> class Database(ProfessionalAuthMixin):
        ...     def __init__(self):
        ...         self.client = None
        ...         self.is_real = False
        ...         self.mock = {"professionals": {}}
        
        >>> db = Database()
        >>> pro = db.create_professional(
        ...     email="nutri@example.com",
        ...     password="password123",
        ...     name="Dr. João Silva",
        ...     specialty=Specialty.NUTRITIONIST,
        ...     crn="CRN-12345"
        ... )
        >>> if pro:
        ...     print(f"Profissional criado: {pro.name}")
    """

    # ─────────────────────────────────────────────────────────────────────────
    # AUTENTICAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def get_professional(self, email: str, password: str) -> Professional | None:
        """
        Autentica um profissional de saúde.
        
        Args:
            email: Email do profissional
            password: Senha em texto puro
            
        Returns:
            Professional se autenticado, None caso contrário
            
        Example:
            >>> pro = db.get_professional("nutri@example.com", "password123")
            >>> if pro:
            ...     print(f"Login realizado: {pro.name}")
            ... else:
            ...     print("Credenciais inválidas")
        """
        email_lower = email.lower().strip()
        
        # 1. Tenta Supabase
        if self.is_real and self.client:
            try:
                # Busca profissional no banco
                response = (
                    self.client.table("profissionais")
                    .select("*")
                    .eq("email", email_lower)
                    .limit(1)
                    .execute()
                )
                
                if response.data:
                    professional_data = response.data[0]
                    
                    # Verifica senha
                    stored_hash = professional_data.get("password_hash", "")
                    
                    if verify_password(password, stored_hash):
                        professional = self._build_professional_from_data(professional_data)
                        logger.info(f"✅ Login profissional (Supabase): {email_lower}")
                        return professional
                    else:
                        logger.warning(f"❌ Senha incorreta para: {email_lower}")
                        return None
                
            except Exception as e:
                logger.error(f"get_professional Supabase: {e}")
        
        # 2. Fallback MockDB
        professional_data = self.mock.get("professionals", {}).get(email_lower)
        
        if not professional_data:
            logger.warning(f"❌ Profissional não encontrado: {email_lower}")
            return None
        
        # Verifica senha
        stored_hash = professional_data.get("password_hash", "")
        
        if not verify_password(password, stored_hash):
            logger.warning(f"❌ Senha incorreta para: {email_lower}")
            return None
        
        professional = self._build_professional_from_data(professional_data)
        logger.info(f"✅ Login profissional (MockDB): {email_lower}")
        return professional

    # ─────────────────────────────────────────────────────────────────────────
    # CRIAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def create_professional(
        self,
        email: str,
        password: str,
        name: str,
        specialty: Specialty = Specialty.NUTRITIONIST,
        crn: str = "",
    ) -> Professional | None:
        """
        Cria um novo profissional de saúde.
        
        Args:
            email: Email do profissional
            password: Senha em texto puro
            name: Nome completo
            specialty: Especialidade
            crn: Número de registro (CRN/CRM)
            
        Returns:
            Professional criado ou None se já existe ou dados inválidos
            
        Example:
            >>> pro = db.create_professional(
            ...     email="nutri@example.com",
            ...     password="password123",
            ...     name="Dr. João Silva",
            ...     specialty=Specialty.NUTRITIONIST,
            ...     crn="CRN-12345"
            ... )
            >>> if pro:
            ...     print(f"Profissional criado: {pro.email}")
            ... else:
            ...     print("Email já cadastrado ou dados inválidos")
        """
        email_lower = email.lower().strip()
        
        # Validações
        if not validate_email(email_lower):
            logger.warning(f"❌ Email inválido: {email_lower}")
            return None
        
        if not name or not name.strip():
            logger.warning("❌ Nome é obrigatório")
            return None
        
        password_validation = validate_password(password)
        if not password_validation:
            logger.warning(f"❌ Senha inválida: {password_validation.message}")
            return None
        
        # 1. Tenta Supabase
        if self.is_real and self.client:
            try:
                # Cria usuário no Supabase Auth
                auth_response = self.client.auth.sign_up({
                    "email": email_lower,
                    "password": password,
                    "options": {
                        "data": {
                            "name": name,
                            "role": "professional",
                        }
                    },
                })
                
                if auth_response.user:
                    # Calcula trial_end
                    trial_end = (
                        datetime.now(timezone.utc) + timedelta(days=config.TRIAL_DAYS)
                    ).isoformat()
                    
                    # Cria perfil profissional
                    self.client.table("profissionais").insert({
                        "usuario_id": auth_response.user.id,
                        "email": email_lower,
                        "nome_completo": name,
                        "especialidade": specialty.value,
                        "crn": crn,
                        "password_hash": hash_password(password),
                        "plan": "trial",
                        "trial_end": trial_end,
                    }).execute()
                    
                    # Busca perfil criado
                    profile_response = (
                        self.client.table("profissionais")
                        .select("*")
                        .eq("email", email_lower)
                        .limit(1)
                        .execute()
                    )
                    
                    if profile_response.data:
                        professional = self._build_professional_from_data(profile_response.data[0])
                        logger.info(f"✅ Profissional criado no Supabase: {email_lower}")
                        return professional
                
            except Exception as e:
                logger.error(f"create_professional Supabase: {e}")
        
        # 2. Fallback MockDB
        professionals = self.mock.setdefault("professionals", {})
        
        if email_lower in professionals:
            logger.warning(f"❌ Email já existe: {email_lower}")
            return None
        
        # Calcula trial_end
        trial_end = (
            datetime.now(timezone.utc) + timedelta(days=config.TRIAL_DAYS)
        ).isoformat()
        
        # Cria profissional no MockDB
        professional_data = {
            "email": email_lower,
            "name": name,
            "specialty": specialty.value,
            "crn": crn,
            "password_hash": hash_password(password),
            "plan": "trial",
            "trial_end": trial_end,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        professionals[email_lower] = professional_data
        
        professional = self._build_professional_from_data(professional_data)
        logger.info(f"✅ Profissional criado no MockDB: {email_lower}")
        return professional

    # ─────────────────────────────────────────────────────────────────────────
    # BUSCA
    # ─────────────────────────────────────────────────────────────────────────

    def get_professional_by_email(self, email: str) -> Professional | None:
        """
        Busca um profissional pelo email (sem autenticação).
        
        Args:
            email: Email do profissional
            
        Returns:
            Professional se encontrado, None caso contrário
            
        Example:
            >>> pro = db.get_professional_by_email("nutri@example.com")
            >>> if pro:
            ...     print(f"Profissional encontrado: {pro.name}")
            ... else:
            ...     print("Profissional não encontrado")
        """
        email_lower = email.lower().strip()
        
        # 1. Tenta Supabase
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("profissionais")
                    .select("*")
                    .eq("email", email_lower)
                    .limit(1)
                    .execute()
                )
                
                if response.data:
                    return self._build_professional_from_data(response.data[0])
                
            except Exception as e:
                logger.error(f"get_professional_by_email Supabase: {e}")
        
        # 2. Fallback MockDB
        professional_data = self.mock.get("professionals", {}).get(email_lower)
        
        if not professional_data:
            logger.debug(f"Profissional não encontrado: {email_lower}")
            return None
        
        return self._build_professional_from_data(professional_data)

    # ─────────────────────────────────────────────────────────────────────────
    # ATUALIZAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def update_professional(self, email: str, data: dict[str, Any]) -> bool:
        """
        Atualiza dados de um profissional.
        
        Args:
            email: Email do profissional
            data: Dicionário com campos a atualizar
            
        Returns:
            True se atualizado com sucesso, False caso contrário
            
        Example:
            >>> success = db.update_professional(
            ...     "nutri@example.com",
            ...     {"name": "Dr. João Silva Jr.", "crn": "CRN-67890"}
            ... )
            >>> if success:
            ...     print("Profissional atualizado!")
        """
        email_lower = email.lower().strip()
        
        # Mapeamento de campos Python → Supabase
        field_map = {
            "name": "nome_completo",
            "specialty": "especialidade",
            "crn": "crn",
            "plan": "plan",
        }
        
        # 1. Tenta Supabase
        if self.is_real and self.client:
            try:
                # Converte campos para formato do Supabase
                payload = {}
                for key, value in data.items():
                    # Converte Enum para string
                    if hasattr(value, "value"):
                        value = value.value
                    
                    # Mapeia nome do campo
                    db_field = field_map.get(key, key)
                    payload[db_field] = value
                
                response = (
                    self.client.table("profissionais")
                    .update(payload)
                    .eq("email", email_lower)
                    .execute()
                )
                
                if response.data:
                    logger.info(f"✅ Profissional atualizado no Supabase: {email_lower}")
                    return True
                
            except Exception as e:
                logger.error(f"update_professional Supabase: {e}")
        
        # 2. Fallback MockDB
        professionals = self.mock.get("professionals", {})
        professional_data = professionals.get(email_lower)
        
        if not professional_data:
            logger.warning(f"❌ Profissional não encontrado: {email_lower}")
            return False
        
        # Atualiza dados
        professional_data.update(data)
        logger.info(f"✅ Profissional atualizado no MockDB: {email_lower}")
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # REMOÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def delete_professional(self, email: str) -> bool:
        """
        Remove um profissional.
        
        Args:
            email: Email do profissional
            
        Returns:
            True se removido com sucesso, False caso contrário
            
        Example:
            >>> success = db.delete_professional("nutri@example.com")
            >>> if success:
            ...     print("Profissional removido!")
        """
        email_lower = email.lower().strip()
        
        # 1. Tenta Supabase
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("profissionais")
                    .delete()
                    .eq("email", email_lower)
                    .execute()
                )
                
                if response.data:
                    logger.info(f"✅ Profissional removido do Supabase: {email_lower}")
                    return True
                
            except Exception as e:
                logger.error(f"delete_professional Supabase: {e}")
        
        # 2. Fallback MockDB
        professionals = self.mock.get("professionals", {})
        
        if email_lower not in professionals:
            logger.warning(f"❌ Profissional não encontrado: {email_lower}")
            return False
        
        del professionals[email_lower]
        logger.info(f"✅ Profissional removido do MockDB: {email_lower}")
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # HELPER DE CONVERSÃO
    # ─────────────────────────────────────────────────────────────────────────

    def _build_professional_from_data(self, data: dict[str, Any]) -> Professional:
        """
        Converte um dicionário para um objeto Professional.
        
        Centraliza a lógica de conversão para evitar duplicação.
        
        Args:
            data: Dicionário com dados do profissional
            
        Returns:
            Instância de Professional
            
        Example:
            >>> pro = db._build_professional_from_data({
            ...     "email": "nutri@example.com",
            ...     "name": "Dr. João",
            ...     "specialty": "nutritionist"
            ... })
        """
        # Converte specialty string para Enum
        try:
            specialty = Specialty(data.get("specialty", "nutritionist"))
        except ValueError:
            logger.debug(f"Specialty inválida, usando padrão: {data.get('specialty')}")
            specialty = Specialty.NUTRITIONIST
        
        # Converte created_at
        created_at_str = data.get("created_at")
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str)
            except ValueError:
                logger.debug(f"created_at inválido, usando agora")
                created_at = datetime.now(timezone.utc)
        else:
            created_at = datetime.now(timezone.utc)
        
        # Converte plan
        plan_str = data.get("plan", "trial")
        try:
            plan = Plan(plan_str)
        except ValueError:
            logger.debug(f"Plan inválido, usando trial: {plan_str}")
            plan = Plan.TRIAL
        
        return Professional(
            email=data.get("email", ""),
            name=data.get("name", data.get("nome_completo", "")),
            specialty=specialty,
            crn=data.get("crn", data.get("crn_number", "")),
            password_hash="",  # Não retornamos o hash
            plan=plan,
            created_at=created_at,
        )


__all__ = ["ProfessionalAuthMixin"]
