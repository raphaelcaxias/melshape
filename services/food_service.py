"""
Melshape — Food Service.

Gerencia o banco de alimentos com cache, busca normalizada e fallback local.

Princípios:
- Cache: 1 hora por categoria e busca (st.cache_data)
- Busca normalizada: sem acentos, case-insensitive
- Fallback: Supabase → 60+ alimentos TACO
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para todas as entidades

Arquitetura:
    FoodService
    ├── Search
    │   ├── search(query, category, limit) -> FoodSearchResult
    │   ├── search_with_result(query, category, limit) -> FoodSearchResult
    │   ├── get_by_category(category) -> list[FoodItem]
    │   ├── get_all() -> list[FoodItem]
    │   └── get_popular_foods(limit) -> list[FoodItem]
    ├── Lookup
    │   ├── get_food_by_id(food_id) -> FoodItem | None
    │   └── get_foods_by_ids(food_ids) -> list[FoodItem]
    ├── Categories
    │   ├── get_categories() -> list[FoodCategory]
    │   └── count_by_category(category) -> int
    ├── Cache
    │   ├── _cached_search(query, category) -> list[FoodItem]
    │   └── _cached_by_category(category) -> list[FoodItem]
    ├── Normalization
    │   └── _normalize(text) -> str
    └── Fallback
        └── _get_fallback_foods() -> list[FoodItem]
"""
from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import streamlit as st

logger = logging.getLogger("Melshape.Food")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Limites de busca
_DEFAULT_SEARCH_LIMIT: int = 30
_DEFAULT_CATEGORY_LIMIT: int = 50
_DEFAULT_POPULAR_LIMIT: int = 20

# TTL do cache (1 hora)
_CACHE_TTL: int = 3600

# Thresholds nutricionais
_LOW_CALORIE_THRESHOLD: float = 100.0
_HIGH_PROTEIN_THRESHOLD: float = 20.0
_HIGH_FIBER_THRESHOLD: float = 5.0
_BALANCED_PROTEIN_MIN: float = 15.0
_BALANCED_PROTEIN_MAX: float = 40.0
_BALANCED_CARBS_MIN: float = 20.0
_BALANCED_CARBS_MAX: float = 60.0
_BALANCED_FAT_MAX: float = 20.0

# Alimentos populares (IDs do fallback)
_POPULAR_FOOD_IDS: list[str] = [
    "frango_p", "arroz_int", "feijao_c", "ovo_cozido", "banana",
    "aveia", "batata_doce", "tilapia", "whey", "iog_grego",
]


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class FoodCategoryType(str, Enum):
    """Categorias de alimentos disponíveis."""
    CAFE_MANHA = "cafe_manha"
    ALMOCO_JANTAR = "almoco_jantar"
    LANCHE = "lanche"
    PRE_POS_TREINO = "pre_pos_treino"
    CEIA = "ceia"
    
    @property
    def label(self) -> str:
        """Retorna label da categoria."""
        labels = {
            "cafe_manha": "Café da Manhã",
            "almoco_jantar": "Almoço / Jantar",
            "lanche": "Lanche",
            "pre_pos_treino": "Pré/Pós Treino",
            "ceia": "Ceia",
        }
        return labels.get(self.value, self.value)
    
    @property
    def icon(self) -> str:
        """Retorna ícone da categoria."""
        icons = {
            "cafe_manha": "☕",
            "almoco_jantar": "🍽️",
            "lanche": "🍎",
            "pre_pos_treino": "💪",
            "ceia": "🌙",
        }
        return icons.get(self.value, "🍴")
    
    @classmethod
    def from_string(cls, category: str) -> FoodCategoryType | None:
        """Converte string para enum."""
        try:
            return cls(category)
        except ValueError:
            return None


# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK LOCAL: 60+ ALIMENTOS TACO
# ─────────────────────────────────────────────────────────────────────────────

_FALLBACK_FOODS: dict[str, dict[str, Any]] = {
    # CAFÉ DA MANHÃ
    "pao_frances": {
        "name": "Pão Francês", "category": "cafe_manha",
        "calories": 300, "protein": 8.0, "carbs": 58.0, "fat": 3.0, "fiber": 1.5,
        "portion": "1 unidade (50g)",
    },
    "pao_integral": {
        "name": "Pão Integral", "category": "cafe_manha",
        "calories": 65, "protein": 3.0, "carbs": 12.0, "fat": 1.0, "fiber": 2.0,
        "portion": "1 fatia (25g)",
    },
    "ovo_cozido": {
        "name": "Ovo Cozido", "category": "cafe_manha",
        "calories": 77, "protein": 6.5, "carbs": 0.6, "fat": 5.3, "fiber": 0.0,
        "portion": "1 unidade (50g)",
    },
    "ovo_mexido": {
        "name": "Ovo Mexido", "category": "cafe_manha",
        "calories": 91, "protein": 6.7, "carbs": 0.6, "fat": 7.0, "fiber": 0.0,
        "portion": "1 unidade (55g)",
    },
    "leite_int": {
        "name": "Leite Integral", "category": "cafe_manha",
        "calories": 60, "protein": 3.0, "carbs": 4.5, "fat": 3.3, "fiber": 0.0,
        "portion": "100ml",
    },
    "leite_des": {
        "name": "Leite Desnatado", "category": "cafe_manha",
        "calories": 35, "protein": 3.4, "carbs": 5.0, "fat": 0.1, "fiber": 0.0,
        "portion": "100ml",
    },
    "cafe_leite": {
        "name": "Café com Leite", "category": "cafe_manha",
        "calories": 50, "protein": 2.0, "carbs": 5.0, "fat": 2.0, "fiber": 0.0,
        "portion": "200ml",
    },
    "tapioca": {
        "name": "Tapioca", "category": "cafe_manha",
        "calories": 130, "protein": 0.5, "carbs": 32.0, "fat": 0.1, "fiber": 0.4,
        "portion": "1 unidade (50g)",
    },
    "iog_natural": {
        "name": "Iogurte Natural", "category": "cafe_manha",
        "calories": 61, "protein": 3.5, "carbs": 4.7, "fat": 3.3, "fiber": 0.0,
        "portion": "100g",
    },
    "iog_grego": {
        "name": "Iogurte Grego", "category": "cafe_manha",
        "calories": 115, "protein": 8.5, "carbs": 4.0, "fat": 6.5, "fiber": 0.0,
        "portion": "100g",
    },
    "aveia": {
        "name": "Aveia em Flocos", "category": "cafe_manha",
        "calories": 360, "protein": 13.0, "carbs": 64.0, "fat": 6.9, "fiber": 9.4,
        "portion": "100g",
    },
    "granola": {
        "name": "Granola", "category": "cafe_manha",
        "calories": 420, "protein": 10.0, "carbs": 65.0, "fat": 14.0, "fiber": 7.0,
        "portion": "100g",
    },
    "queijo_minas": {
        "name": "Queijo Minas Frescal", "category": "cafe_manha",
        "calories": 264, "protein": 17.0, "carbs": 3.2, "fat": 20.0, "fiber": 0.0,
        "portion": "100g",
    },
    "mamao": {
        "name": "Mamão Papaia", "category": "cafe_manha",
        "calories": 45, "protein": 0.5, "carbs": 11.8, "fat": 0.1, "fiber": 1.8,
        "portion": "100g",
    },
    "cuscuz": {
        "name": "Cuscuz Nordestino", "category": "cafe_manha",
        "calories": 120, "protein": 2.0, "carbs": 28.0, "fat": 0.5, "fiber": 1.0,
        "portion": "100g",
    },
    # ALMOÇO / JANTAR
    "arroz_b": {
        "name": "Arroz Branco Cozido", "category": "almoco_jantar",
        "calories": 128, "protein": 2.5, "carbs": 28.0, "fat": 0.2, "fiber": 0.2,
        "portion": "100g",
    },
    "arroz_int": {
        "name": "Arroz Integral Cozido", "category": "almoco_jantar",
        "calories": 124, "protein": 2.8, "carbs": 26.0, "fat": 0.8, "fiber": 1.7,
        "portion": "100g",
    },
    "feijao_p": {
        "name": "Feijão Preto Cozido", "category": "almoco_jantar",
        "calories": 77, "protein": 4.5, "carbs": 14.0, "fat": 0.5, "fiber": 6.3,
        "portion": "100g",
    },
    "feijao_c": {
        "name": "Feijão Carioca Cozido", "category": "almoco_jantar",
        "calories": 76, "protein": 4.8, "carbs": 13.6, "fat": 0.5, "fiber": 6.4,
        "portion": "100g",
    },
    "frango_p": {
        "name": "Peito de Frango Grelhado", "category": "almoco_jantar",
        "calories": 159, "protein": 32.0, "carbs": 0.0, "fat": 3.5, "fiber": 0.0,
        "portion": "100g",
    },
    "frango_c": {
        "name": "Coxa de Frango Assada", "category": "almoco_jantar",
        "calories": 204, "protein": 25.0, "carbs": 0.0, "fat": 11.5, "fiber": 0.0,
        "portion": "100g",
    },
    "patinho": {
        "name": "Patinho Bovino Grelhado", "category": "almoco_jantar",
        "calories": 219, "protein": 33.0, "carbs": 0.0, "fat": 9.0, "fiber": 0.0,
        "portion": "100g",
    },
    "carne_moida": {
        "name": "Carne Moída Refogada", "category": "almoco_jantar",
        "calories": 265, "protein": 25.0, "carbs": 5.0, "fat": 16.0, "fiber": 0.0,
        "portion": "100g",
    },
    "tilapia": {
        "name": "Tilápia Assada", "category": "almoco_jantar",
        "calories": 128, "protein": 26.0, "carbs": 0.0, "fat": 2.7, "fiber": 0.0,
        "portion": "100g",
    },
    "atum_lata": {
        "name": "Atum em Lata (água)", "category": "almoco_jantar",
        "calories": 116, "protein": 26.0, "carbs": 0.0, "fat": 1.0, "fiber": 0.0,
        "portion": "100g",
    },
    "salmao": {
        "name": "Salmão Grelhado", "category": "almoco_jantar",
        "calories": 206, "protein": 28.0, "carbs": 0.0, "fat": 10.0, "fiber": 0.0,
        "portion": "100g",
    },
    "ovo_frito": {
        "name": "Ovo Frito", "category": "almoco_jantar",
        "calories": 109, "protein": 7.0, "carbs": 0.4, "fat": 9.0, "fiber": 0.0,
        "portion": "1 unidade (55g)",
    },
    "macarrao": {
        "name": "Macarrão Cozido", "category": "almoco_jantar",
        "calories": 131, "protein": 4.5, "carbs": 27.2, "fat": 0.9, "fiber": 1.2,
        "portion": "100g",
    },
    "batata": {
        "name": "Batata Cozida", "category": "almoco_jantar",
        "calories": 87, "protein": 1.9, "carbs": 20.0, "fat": 0.1, "fiber": 1.8,
        "portion": "100g",
    },
    "batata_doce": {
        "name": "Batata Doce Cozida", "category": "almoco_jantar",
        "calories": 86, "protein": 1.4, "carbs": 20.1, "fat": 0.1, "fiber": 2.5,
        "portion": "100g",
    },
    "alface": {
        "name": "Alface", "category": "almoco_jantar",
        "calories": 15, "protein": 1.4, "carbs": 2.9, "fat": 0.2, "fiber": 2.0,
        "portion": "100g",
    },
    "tomate": {
        "name": "Tomate", "category": "almoco_jantar",
        "calories": 18, "protein": 0.9, "carbs": 3.5, "fat": 0.2, "fiber": 1.2,
        "portion": "100g",
    },
    "cenoura": {
        "name": "Cenoura Crua", "category": "almoco_jantar",
        "calories": 34, "protein": 0.9, "carbs": 7.7, "fat": 0.2, "fiber": 3.2,
        "portion": "100g",
    },
    "brocolis": {
        "name": "Brócolis Cozido", "category": "almoco_jantar",
        "calories": 25, "protein": 2.9, "carbs": 3.5, "fat": 0.4, "fiber": 3.3,
        "portion": "100g",
    },
    "pf_completo": {
        "name": "PF: Arroz+Feijão+Frango", "category": "almoco_jantar",
        "calories": 520, "protein": 38.0, "carbs": 64.0, "fat": 8.0, "fiber": 6.0,
        "portion": "1 prato (400g)",
    },
    "sardinha": {
        "name": "Sardinha em Lata", "category": "almoco_jantar",
        "calories": 208, "protein": 24.0, "carbs": 0.0, "fat": 12.0, "fiber": 0.0,
        "portion": "100g",
    },
    "mandioca": {
        "name": "Mandioca Cozida", "category": "almoco_jantar",
        "calories": 150, "protein": 1.0, "carbs": 36.5, "fat": 0.3, "fiber": 1.8,
        "portion": "100g",
    },
    # LANCHE
    "banana": {
        "name": "Banana Prata", "category": "lanche",
        "calories": 98, "protein": 1.3, "carbs": 26.0, "fat": 0.1, "fiber": 2.0,
        "portion": "1 unidade (100g)",
    },
    "maca": {
        "name": "Maçã", "category": "lanche",
        "calories": 56, "protein": 0.3, "carbs": 15.2, "fat": 0.1, "fiber": 2.4,
        "portion": "1 unidade (100g)",
    },
    "laranja": {
        "name": "Laranja", "category": "lanche",
        "calories": 47, "protein": 0.9, "carbs": 11.7, "fat": 0.1, "fiber": 2.4,
        "portion": "1 unidade (130g)",
    },
    "manga": {
        "name": "Manga", "category": "lanche",
        "calories": 60, "protein": 0.8, "carbs": 14.9, "fat": 0.3, "fiber": 1.8,
        "portion": "100g",
    },
    "castanha": {
        "name": "Castanha de Caju", "category": "lanche",
        "calories": 570, "protein": 15.0, "carbs": 32.0, "fat": 46.0, "fiber": 3.7,
        "portion": "100g",
    },
    "amendoim": {
        "name": "Amendoim Torrado", "category": "lanche",
        "calories": 567, "protein": 26.0, "carbs": 16.0, "fat": 49.0, "fiber": 8.5,
        "portion": "100g",
    },
    "pao_queijo": {
        "name": "Pão de Queijo", "category": "lanche",
        "calories": 370, "protein": 6.0, "carbs": 52.0, "fat": 16.0, "fiber": 0.5,
        "portion": "1 unidade (60g)",
    },
    "acai": {
        "name": "Açaí com Granola", "category": "lanche",
        "calories": 280, "protein": 4.0, "carbs": 42.0, "fat": 12.0, "fiber": 5.0,
        "portion": "300ml",
    },
    "kiwi": {
        "name": "Kiwi", "category": "lanche",
        "calories": 61, "protein": 1.1, "carbs": 15.0, "fat": 0.5, "fiber": 3.0,
        "portion": "2 unidades (100g)",
    },
    # PRÉ/PÓS TREINO
    "whey": {
        "name": "Proteína Whey", "category": "pre_pos_treino",
        "calories": 120, "protein": 24.0, "carbs": 3.0, "fat": 2.0, "fiber": 0.0,
        "portion": "1 scoop (30g)",
    },
    "barra_prot": {
        "name": "Barra de Proteína", "category": "pre_pos_treino",
        "calories": 200, "protein": 20.0, "carbs": 22.0, "fat": 6.0, "fiber": 2.0,
        "portion": "1 unidade (60g)",
    },
    "banana_pre": {
        "name": "Banana (pré-treino)", "category": "pre_pos_treino",
        "calories": 98, "protein": 1.3, "carbs": 26.0, "fat": 0.1, "fiber": 2.0,
        "portion": "1 unidade",
    },
    # CEIA
    "leite_quente": {
        "name": "Leite Quente com Mel", "category": "ceia",
        "calories": 90, "protein": 3.0, "carbs": 12.0, "fat": 3.0, "fiber": 0.0,
        "portion": "200ml",
    },
    "cha": {
        "name": "Chá de Camomila", "category": "ceia",
        "calories": 2, "protein": 0.0, "carbs": 0.5, "fat": 0.0, "fiber": 0.0,
        "portion": "200ml",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DO SERVIÇO DE ALIMENTOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FoodItem:
    """
    Modelo de item alimentar.
    
    Attributes:
        id: ID único do alimento (ou chave do fallback)
        name: Nome do alimento
        category: Categoria do alimento
        calories: Calorias por 100g (kcal)
        protein: Proteína por 100g (g)
        carbs: Carboidratos por 100g (g)
        fat: Gorduras por 100g (g)
        fiber: Fibras por 100g (g)
        portion: Porção padrão
        is_active: Se está ativo no banco
    """
    id: str
    name: str
    category: str
    calories: float
    protein: float
    carbs: float
    fat: float
    fiber: float = 0.0
    portion: str = ""
    is_active: bool = True
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FoodItem:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", data.get("key", "")),
            name=data.get("name", data.get("nome", "")),
            category=data.get("category", data.get("categoria", "")),
            calories=float(data.get("calories", data.get("calorias", 0))),
            protein=float(data.get("protein", data.get("proteina", 0))),
            carbs=float(data.get("carbs", data.get("carboidratos", 0))),
            fat=float(data.get("fat", data.get("gorduras", 0))),
            fiber=float(data.get("fiber", data.get("fibra", 0))),
            portion=data.get("portion", data.get("porcao", "")),
            is_active=data.get("is_active", data.get("ativo", True)),
        )
    
    @property
    def calories_per_100g(self) -> float:
        """Retorna calorias por 100g."""
        return self.calories
    
    @property
    def protein_per_100g(self) -> float:
        """Retorna proteína por 100g."""
        return self.protein
    
    @property
    def carbs_per_100g(self) -> float:
        """Retorna carboidratos por 100g."""
        return self.carbs
    
    @property
    def fat_per_100g(self) -> float:
        """Retorna gorduras por 100g."""
        return self.fat
    
    @property
    def fiber_per_100g(self) -> float:
        """Retorna fibras por 100g."""
        return self.fiber
    
    @property
    def display_name(self) -> str:
        """Retorna nome formatado para exibição."""
        return f"{self.name} ({self.calories:.0f} kcal/100g)"
    
    @property
    def macro_summary(self) -> str:
        """Retorna resumo dos macros."""
        return f"P: {self.protein:.1f}g | C: {self.carbs:.1f}g | G: {self.fat:.1f}g"
    
    @property
    def is_low_calorie(self) -> bool:
        """Verifica se é um alimento de baixa caloria (< 100 kcal/100g)."""
        return self.calories < _LOW_CALORIE_THRESHOLD
    
    @property
    def is_high_protein(self) -> bool:
        """Verifica se é um alimento rico em proteína (> 20g/100g)."""
        return self.protein > _HIGH_PROTEIN_THRESHOLD
    
    @property
    def is_high_fiber(self) -> bool:
        """Verifica se é um alimento rico em fibras (> 5g/100g)."""
        return self.fiber > _HIGH_FIBER_THRESHOLD
    
    @property
    def is_balanced(self) -> bool:
        """Verifica se é um alimento balanceado (macros equilibrados)."""
        return (
            _BALANCED_PROTEIN_MIN <= self.protein <= _BALANCED_PROTEIN_MAX
            and _BALANCED_CARBS_MIN <= self.carbs <= _BALANCED_CARBS_MAX
            and self.fat <= _BALANCED_FAT_MAX
        )
    
    @property
    def protein_ratio(self) -> float:
        """Retorna percentual de calorias vindas de proteína."""
        if self.calories == 0:
            return 0.0
        protein_calories = self.protein * 4
        return (protein_calories / self.calories) * 100
    
    @property
    def carbs_ratio(self) -> float:
        """Retorna percentual de calorias vindas de carboidratos."""
        if self.calories == 0:
            return 0.0
        carbs_calories = self.carbs * 4
        return (carbs_calories / self.calories) * 100
    
    @property
    def fat_ratio(self) -> float:
        """Retorna percentual de calorias vindas de gordura."""
        if self.calories == 0:
            return 0.0
        fat_calories = self.fat * 9
        return (fat_calories / self.calories) * 100
    
    @property
    def nutri_score(self) -> int:
        """
        Calcula score nutricional simplificado (0-100).
        
        Critérios:
        - Proteína alta: +30
        - Fibras altas: +20
        - Baixa caloria: +20
        - Balanceado: +30
        """
        score = 0
        
        if self.is_high_protein:
            score += 30
        elif self.protein > 10:
            score += 15
        
        if self.is_high_fiber:
            score += 20
        elif self.fiber > 2:
            score += 10
        
        if self.is_low_calorie:
            score += 20
        
        if self.is_balanced:
            score += 30
        
        return min(100, score)
    
    @property
    def nutri_label(self) -> str:
        """Retorna label do score nutricional."""
        score = self.nutri_score
        if score >= 80:
            return "🏆 Excelente"
        elif score >= 60:
            return "✅ Muito bom"
        elif score >= 40:
            return "👍 Bom"
        elif score >= 20:
            return "⚠️ Regular"
        return "❌ Fraco"
    
    @property
    def category_enum(self) -> FoodCategoryType | None:
        """Retorna enum da categoria."""
        return FoodCategoryType.from_string(self.category)
    
    @property
    def category_label(self) -> str:
        """Retorna label da categoria."""
        cat_enum = self.category_enum
        return cat_enum.label if cat_enum else self.category


@dataclass(frozen=True)
class FoodCategory:
    """
    Modelo de categoria de alimentos.
    
    Attributes:
        code: Código da categoria
        label: Nome legível da categoria
        icon: Ícone representativo
        count: Quantidade de alimentos na categoria
    """
    code: str
    label: str
    icon: str
    count: int = 0
    
    @classmethod
    def from_enum(cls, enum: FoodCategoryType, count: int = 0) -> FoodCategory:
        """Cria uma categoria a partir do enum."""
        return cls(
            code=enum.value,
            label=enum.label,
            icon=enum.icon,
            count=count,
        )
    
    @property
    def display_text(self) -> str:
        """Retorna texto formatado para exibição."""
        return f"{self.icon} {self.label} ({self.count})"


@dataclass(frozen=True)
class FoodSearchResult:
    """
    Resultado de uma busca de alimentos.
    
    Attributes:
        query: Termo buscado
        items: Lista de alimentos encontrados
        total: Total de resultados
        category: Categoria filtrada (se houver)
        from_cache: Se veio do cache
        from_supabase: Se veio do Supabase
        search_time_ms: Tempo de busca em milissegundos
    """
    query: str
    items: list[FoodItem]
    total: int
    category: str | None = None
    from_cache: bool = False
    from_supabase: bool = False
    search_time_ms: float = 0.0
    
    @property
    def has_results(self) -> bool:
        """Verifica se há resultados."""
        return self.total > 0
    
    @property
    def first_item(self) -> FoodItem | None:
        """Retorna o primeiro item."""
        return self.items[0] if self.items else None
    
    @property
    def source_label(self) -> str:
        """Retorna label da fonte dos dados."""
        if self.from_cache:
            return "📦 Cache"
        elif self.from_supabase:
            return "☁️ Supabase"
        return "💾 Local"
    
    @property
    def summary_text(self) -> str:
        """Retorna texto resumido do resultado."""
        if self.has_results:
            return f"{self.total} resultado(s) via {self.source_label}"
        return "Nenhum resultado encontrado"
    
    @property
    def categories_found(self) -> list[str]:
        """Retorna categorias presentes nos resultados."""
        return sorted(set(item.category for item in self.items))


# ─────────────────────────────────────────────────────────────────────────────
# FOOD SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class FoodService:
    """
    Serviço de banco de alimentos.
    
    Gerencia busca com cache, normalização e fallback local.
    
    Example:
        >>> client = supabase_client
        >>> food_service = FoodService(client)
        >>> result = food_service.search("frango")
        >>> for item in result.items:
        ...     print(f"{item.name}: {item.calories} kcal/100g")
    """

    def __init__(self, client: Any | None = None) -> None:
        """
        Inicializa o serviço de alimentos.
        
        Args:
            client: Cliente Supabase (ou None para fallback)
        """
        self.client = client
        self.use_supabase = client is not None
        logger.debug(f"✅ FoodService inicializado (Supabase: {self.use_supabase})")

    # ─────────────────────────────────────────────────────────────────────────
    # SEARCH (com FoodSearchResult)
    # ─────────────────────────────────────────────────────────────────────────

    def search_with_result(
        self,
        query: str,
        category: str | None = None,
        limit: int = _DEFAULT_SEARCH_LIMIT,
    ) -> FoodSearchResult:
        """
        Busca alimentos por termo e retorna resultado rico.
        
        Args:
            query: Termo de busca
            category: Categoria para filtrar (opcional)
            limit: Número máximo de resultados
            
        Returns:
            Objeto FoodSearchResult com resultados e metadados
            
        Example:
            >>> result = food_service.search_with_result("frango")
            >>> print(result.summary_text)
            >>> for item in result.items:
            ...     print(item.display_name)
        """
        import time
        start_time = time.time()
        
        if not query or len(query.strip()) < 2:
            logger.debug("search_with_result: query muito curta")
            return FoodSearchResult(
                query=query or "",
                items=[],
                total=0,
                category=category,
            )

        query = query.strip()
        normalized_query = self._normalize(query)

        from_supabase = False
        from_cache = False

        # 1. Tenta cache primeiro
        cached_items = self._cached_search(normalized_query, category)
        if cached_items is not None:
            from_cache = True
            items = cached_items[:limit]
            logger.debug(f"✅ {len(items)} resultados do cache para '{query}'")
        else:
            # 2. Tenta Supabase
            if self.use_supabase:
                try:
                    items = self._search_supabase(normalized_query, category, limit)
                    if items:
                        from_supabase = True
                        logger.debug(f"✅ {len(items)} resultados do Supabase para '{query}'")
                    else:
                        # 3. Fallback local
                        items = self._search_fallback(normalized_query, category, limit)
                        logger.debug(f"✅ {len(items)} resultados do fallback para '{query}'")
                except Exception as e:
                    logger.warning(f"search Supabase falhou: {e}")
                    items = self._search_fallback(normalized_query, category, limit)
            else:
                # Fallback local
                items = self._search_fallback(normalized_query, category, limit)
                logger.debug(f"✅ {len(items)} resultados do fallback para '{query}'")
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        result = FoodSearchResult(
            query=query,
            items=items,
            total=len(items),
            category=category,
            from_cache=from_cache,
            from_supabase=from_supabase,
            search_time_ms=round(elapsed_ms, 2),
        )
        
        logger.debug(f"✅ Busca concluída em {elapsed_ms:.2f}ms: {result.summary_text}")
        return result

    def search(
        self,
        query: str,
        category: str | None = None,
        limit: int = _DEFAULT_SEARCH_LIMIT,
    ) -> list[FoodItem]:
        """
        Busca alimentos por termo (retorna apenas lista).
        
        Args:
            query: Termo de busca
            category: Categoria para filtrar (opcional)
            limit: Número máximo de resultados
            
        Returns:
            Lista de objetos FoodItem
            
        Example:
            >>> items = food_service.search("frango", limit=10)
            >>> for item in items:
            ...     print(item.display_name)
        """
        result = self.search_with_result(query, category, limit)
        return result.items

    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY LOOKUP
    # ─────────────────────────────────────────────────────────────────────────

    def get_by_category(self, category: str) -> list[FoodItem]:
        """
        Retorna alimentos de uma categoria.
        
        Args:
            category: Categoria (cafe_manha/almoco_jantar/lanche/etc)
            
        Returns:
            Lista de objetos FoodItem
            
        Example:
            >>> items = food_service.get_by_category("lanche")
            >>> for item in items:
            ...     print(item.name)
        """
        if not category:
            logger.warning("get_by_category: category não informado")
            return []

        # 1. Tenta cache
        cached_items = self._cached_by_category(category)
        if cached_items is not None:
            logger.debug(f"✅ {len(cached_items)} itens do cache para categoria {category}")
            return cached_items

        # 2. Tenta Supabase
        if self.use_supabase:
            try:
                results = self._get_category_supabase(category)
                if results:
                    logger.debug(f"✅ {len(results)} resultados do Supabase para categoria {category}")
                    return results
            except Exception as e:
                logger.warning(f"get_by_category Supabase falhou: {e}")

        # 3. Fallback local
        results = self._get_category_fallback(category)
        logger.debug(f"✅ {len(results)} resultados do fallback para categoria {category}")
        return results

    def get_all(self) -> list[FoodItem]:
        """
        Retorna todos os alimentos disponíveis.
        
        Returns:
            Lista de objetos FoodItem
            
        Example:
            >>> all_foods = food_service.get_all()
            >>> print(f"Total: {len(all_foods)} alimentos")
        """
        # 1. Tenta Supabase
        if self.use_supabase:
            try:
                results = self._get_all_supabase()
                if results:
                    logger.debug(f"✅ {len(results)} alimentos do Supabase")
                    return results
            except Exception as e:
                logger.warning(f"get_all Supabase falhou: {e}")

        # 2. Fallback local
        results = self._get_all_fallback()
        logger.debug(f"✅ {len(results)} alimentos do fallback")
        return results

    def get_popular_foods(self, limit: int = _DEFAULT_POPULAR_LIMIT) -> list[FoodItem]:
        """
        Retorna alimentos populares (mais usados).
        
        Args:
            limit: Número máximo de resultados
            
        Returns:
            Lista de objetos FoodItem
            
        Example:
            >>> popular = food_service.get_popular_foods(10)
            >>> for item in popular:
            ...     print(item.display_name)
        """
        if limit <= 0:
            return []
        
        items = []
        for food_id in _POPULAR_FOOD_IDS[:limit]:
            food = self.get_food_by_id(food_id)
            if food:
                items.append(food)
        
        logger.debug(f"✅ {len(items)} alimentos populares retornados")
        return items

    # ─────────────────────────────────────────────────────────────────────────
    # LOOKUP BY ID
    # ─────────────────────────────────────────────────────────────────────────

    def get_food_by_id(self, food_id: str) -> FoodItem | None:
        """
        Busca um alimento pelo ID.
        
        Args:
            food_id: ID do alimento
            
        Returns:
            Objeto FoodItem ou None
            
        Example:
            >>> food = food_service.get_food_by_id("frango_p")
            >>> if food:
            ...     print(food.display_name)
        """
        if not food_id:
            logger.warning("get_food_by_id: food_id não informado")
            return None

        # Tenta fallback local primeiro (mais rápido)
        if food_id in _FALLBACK_FOODS:
            food = FoodItem.from_dict({**_FALLBACK_FOODS[food_id], "id": food_id})
            logger.debug(f"✅ Alimento encontrado no fallback: {food.name}")
            return food

        # Tenta Supabase
        if self.use_supabase:
            try:
                response = (
                    self.client.table("foods")
                    .select("*")
                    .eq("id", food_id)
                    .limit(1)
                    .execute()
                )
                if response.data:
                    food = FoodItem.from_dict(response.data[0])
                    logger.debug(f"✅ Alimento encontrado no Supabase: {food.name}")
                    return food
            except Exception as e:
                logger.debug(f"get_food_by_id Supabase: {e}")

        logger.debug(f"get_food_by_id: alimento não encontrado: {food_id}")
        return None

    def get_foods_by_ids(self, food_ids: list[str]) -> list[FoodItem]:
        """
        Busca múltiplos alimentos por IDs.
        
        Args:
            food_ids: Lista de IDs
            
        Returns:
            Lista de objetos FoodItem encontrados
            
        Example:
            >>> foods = food_service.get_foods_by_ids(["frango_p", "arroz_int", "banana"])
            >>> for food in foods:
            ...     print(food.display_name)
        """
        if not food_ids:
            return []
        
        items = []
        for food_id in food_ids:
            food = self.get_food_by_id(food_id)
            if food:
                items.append(food)
        
        logger.debug(f"✅ {len(items)}/{len(food_ids)} alimentos encontrados")
        return items

    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORIES
    # ─────────────────────────────────────────────────────────────────────────

    def get_categories(self) -> list[FoodCategory]:
        """
        Retorna todas as categorias disponíveis com contagem.
        
        Returns:
            Lista de objetos FoodCategory
            
        Example:
            >>> categories = food_service.get_categories()
            >>> for cat in categories:
            ...     print(cat.display_text)
        """
        # Conta alimentos por categoria no fallback
        category_counts: dict[str, int] = {}
        
        for data in _FALLBACK_FOODS.values():
            category = data.get("category")
            if category:
                category_counts[category] = category_counts.get(category, 0) + 1
        
        # Adiciona categorias do Supabase se disponível
        if self.use_supabase:
            try:
                response = self.client.table("foods").select("category_code").eq("is_active", True).execute()
                for item in (response.data or []):
                    category = item.get("category_code")
                    if category:
                        category_counts[category] = category_counts.get(category, 0) + 1
            except Exception as e:
                logger.debug(f"get_categories Supabase: {e}")
        
        # Cria objetos FoodCategory
        categories = []
        for code, count in sorted(category_counts.items()):
            enum = FoodCategoryType.from_string(code)
            if enum:
                cat = FoodCategory.from_enum(enum, count)
            else:
                cat = FoodCategory(code=code, label=code, icon="🍴", count=count)
            categories.append(cat)
        
        logger.debug(f"✅ {len(categories)} categorias encontradas")
        return categories

    def count_by_category(self, category: str) -> int:
        """
        Conta alimentos em uma categoria.
        
        Args:
            category: Código da categoria
            
        Returns:
            Número de alimentos na categoria
            
        Example:
            >>> count = food_service.count_by_category("lanche")
            >>> print(f"Lanches disponíveis: {count}")
        """
        if not category:
            return 0
        
        items = self.get_by_category(category)
        return len(items)

    # ─────────────────────────────────────────────────────────────────────────
    # SUPABASE QUERIES
    # ─────────────────────────────────────────────────────────────────────────

    def _search_supabase(
        self,
        query: str,
        category: str | None,
        limit: int,
    ) -> list[FoodItem]:
        """Busca no Supabase."""
        if not self.client:
            return []

        try:
            q = (
                self.client.table("foods")
                .select("*")
                .ilike("name", f"%{query}%")
                .eq("is_active", True)
            )

            if category:
                q = q.eq("category_code", category)

            response = q.limit(limit).execute()
            return [FoodItem.from_dict(item) for item in (response.data or [])]

        except Exception as e:
            logger.debug(f"_search_supabase: {e}")
            return []

    def _get_category_supabase(self, category: str) -> list[FoodItem]:
        """Busca categoria no Supabase."""
        if not self.client:
            return []

        try:
            response = (
                self.client.table("foods")
                .select("*")
                .eq("category_code", category)
                .eq("is_active", True)
                .order("name")
                .limit(_DEFAULT_CATEGORY_LIMIT)
                .execute()
            )
            return [FoodItem.from_dict(item) for item in (response.data or [])]

        except Exception as e:
            logger.debug(f"_get_category_supabase: {e}")
            return []

    def _get_all_supabase(self) -> list[FoodItem]:
        """Busca todos os alimentos no Supabase."""
        if not self.client:
            return []

        try:
            response = (
                self.client.table("foods")
                .select("*")
                .eq("is_active", True)
                .order("name")
                .execute()
            )
            return [FoodItem.from_dict(item) for item in (response.data or [])]

        except Exception as e:
            logger.debug(f"_get_all_supabase: {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # CACHE
    # ─────────────────────────────────────────────────────────────────────────

    @st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
    def _cached_search(_self, query: str, category: str | None) -> list[FoodItem] | None:
        """
        Busca com cache (1 hora).
        
        Args:
            query: Query normalizada
            category: Categoria (ou None)
            
        Returns:
            Lista de alimentos ou None se não encontrado
        """
        # Tenta Supabase
        if _self.use_supabase:
            try:
                items = _self._search_supabase(query, category, _DEFAULT_SEARCH_LIMIT)
                if items:
                    return items
            except Exception:
                pass
        
        # Fallback local
        items = _self._search_fallback(query, category, _DEFAULT_SEARCH_LIMIT)
        return items if items else None

    @st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
    def _cached_by_category(_self, category: str) -> list[FoodItem] | None:
        """
        Busca por categoria com cache (1 hora).
        
        Args:
            category: Código da categoria
            
        Returns:
            Lista de alimentos ou None se não encontrado
        """
        # Tenta Supabase
        if _self.use_supabase:
            try:
                items = _self._get_category_supabase(category)
                if items:
                    return items
            except Exception:
                pass
        
        # Fallback local
        items = _self._get_category_fallback(category)
        return items if items else None

    # ─────────────────────────────────────────────────────────────────────────
    # FALLBACK LOCAL
    # ─────────────────────────────────────────────────────────────────────────

    def _search_fallback(
        self,
        query: str,
        category: str | None,
        limit: int,
    ) -> list[FoodItem]:
        """Busca no fallback local."""
        results = []

        for key, data in _FALLBACK_FOODS.items():
            # Filtra por categoria
            if category and data.get("category") != category:
                continue

            # Filtra por termo
            if query:
                normalized_name = self._normalize(data["name"])
                if query not in normalized_name:
                    continue

            results.append(FoodItem.from_dict({**data, "id": key}))

            if len(results) >= limit:
                break

        return results

    def _get_category_fallback(self, category: str) -> list[FoodItem]:
        """Busca categoria no fallback local."""
        results = []

        for key, data in _FALLBACK_FOODS.items():
            if data.get("category") == category:
                results.append(FoodItem.from_dict({**data, "id": key}))

        return results

    def _get_all_fallback(self) -> list[FoodItem]:
        """Busca todos os alimentos no fallback local."""
        return [
            FoodItem.from_dict({**data, "id": key})
            for key, data in _FALLBACK_FOODS.items()
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # NORMALIZAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def _normalize(self, text: str) -> str:
        """
        Normaliza texto: remove acentos, converte para minúsculas.
        
        Args:
            text: Texto a ser normalizado
            
        Returns:
            Texto normalizado
            
        Example:
            >>> food_service._normalize("Açúcar")
            "acucar"
            >>> food_service._normalize("Pão de Queijo")
            "pao de queijo"
        """
        if not text:
            return ""

        # Remove acentos
        nfkd = unicodedata.normalize("NFKD", text.lower())
        normalized = "".join(c for c in nfkd if not unicodedata.combining(c))

        return normalized

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITÁRIOS
    # ─────────────────────────────────────────────────────────────────────────

    def get_total_count(self) -> int:
        """
        Retorna total de alimentos disponíveis.
        
        Returns:
            Número total de alimentos
        """
        return len(self.get_all())

    def search_by_nutrient(
        self,
        min_protein: float | None = None,
        max_calories: float | None = None,
        min_fiber: float | None = None,
        category: str | None = None,
    ) -> list[FoodItem]:
        """
        Busca alimentos por critérios nutricionais.
        
        Args:
            min_protein: Proteína mínima (g/100g)
            max_calories: Calorias máximas (kcal/100g)
            min_fiber: Fibras mínimas (g/100g)
            category: Categoria para filtrar
            
        Returns:
            Lista de alimentos que atendem aos critérios
            
        Example:
            >>> high_protein = food_service.search_by_nutrient(min_protein=20)
            >>> for food in high_protein:
            ...     print(f"{food.name}: {food.protein}g proteína")
        """
        all_foods = self.get_all()
        results = []
        
        for food in all_foods:
            # Filtra por categoria
            if category and food.category != category:
                continue
            
            # Filtra por critérios nutricionais
            if min_protein is not None and food.protein < min_protein:
                continue
            if max_calories is not None and food.calories > max_calories:
                continue
            if min_fiber is not None and food.fiber < min_fiber:
                continue
            
            results.append(food)
        
        logger.debug(f"✅ {len(results)} alimentos encontrados por critérios nutricionais")
        return results

    def get_high_protein_foods(self, min_protein: float = 20.0) -> list[FoodItem]:
        """
        Retorna alimentos ricos em proteína.
        
        Args:
            min_protein: Proteína mínima (g/100g)
            
        Returns:
            Lista de alimentos ricos em proteína
        """
        return self.search_by_nutrient(min_protein=min_protein)

    def get_low_calorie_foods(self, max_calories: float = 100.0) -> list[FoodItem]:
        """
        Retorna alimentos de baixa caloria.
        
        Args:
            max_calories: Calorias máximas (kcal/100g)
            
        Returns:
            Lista de alimentos de baixa caloria
        """
        return self.search_by_nutrient(max_calories=max_calories)


__all__ = [
    "FoodService",
    "FoodItem",
    "FoodCategory",
    "FoodSearchResult",
    "FoodCategoryType",
]
