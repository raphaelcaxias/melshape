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
    # ════════════════════════════════════════════════════════════════════════
    # CAFÉ DA MANHÃ
    # ════════════════════════════════════════════════════════════════════════
    "pao_frances": {"name": "Pão Francês", "category": "cafe_manha", "calories": 150, "protein": 4.0, "carbs": 29.0, "fat": 1.5, "fiber": 0.7, "portion": "1 unidade (50g)"},
    "pao_integral_fatia": {"name": "Pão Integral (fatia)", "category": "cafe_manha", "calories": 56, "protein": 2.3, "carbs": 10.4, "fat": 0.9, "fiber": 1.7, "portion": "1 fatia (25g)"},
    "pao_de_forma": {"name": "Pão de Forma Branco", "category": "cafe_manha", "calories": 66, "protein": 2.1, "carbs": 13.3, "fat": 0.9, "fiber": 0.5, "portion": "1 fatia (25g)"},
    "pao_de_queijo": {"name": "Pão de Queijo", "category": "cafe_manha", "calories": 87, "protein": 1.8, "carbs": 12.5, "fat": 3.5, "fiber": 0.2, "portion": "1 unidade (30g)"},
    "tapioca": {"name": "Tapioca (goma)", "category": "cafe_manha", "calories": 130, "protein": 0.5, "carbs": 32.0, "fat": 0.1, "fiber": 0.4, "portion": "1 unidade (50g)"},
    "cuscuz": {"name": "Cuscuz de Milho Cozido", "category": "cafe_manha", "calories": 103, "protein": 2.2, "carbs": 22.1, "fat": 0.4, "fiber": 1.2, "portion": "1 porção (100g)"},
    "bolo_simples": {"name": "Bolo Simples sem Cobertura", "category": "cafe_manha", "calories": 312, "protein": 5.2, "carbs": 47.0, "fat": 11.5, "fiber": 0.6, "portion": "1 fatia (80g)"},
    "biscoito_agua_sal": {"name": "Biscoito Água e Sal", "category": "cafe_manha", "calories": 130, "protein": 2.5, "carbs": 20.0, "fat": 4.5, "fiber": 0.5, "portion": "6 unidades (30g)"},
    "biscoito_integral": {"name": "Biscoito Integral de Aveia", "category": "cafe_manha", "calories": 122, "protein": 2.8, "carbs": 18.5, "fat": 4.2, "fiber": 1.8, "portion": "4 unidades (30g)"},
    "ovo_cozido": {"name": "Ovo Cozido", "category": "cafe_manha", "calories": 77, "protein": 6.5, "carbs": 0.6, "fat": 5.3, "fiber": 0.0, "portion": "1 unidade (50g)"},
    "ovo_mexido": {"name": "Ovo Mexido", "category": "cafe_manha", "calories": 91, "protein": 6.7, "carbs": 0.6, "fat": 7.0, "fiber": 0.0, "portion": "1 unidade (55g)"},
    "ovo_omelete": {"name": "Omelete Simples", "category": "cafe_manha", "calories": 154, "protein": 12.0, "carbs": 1.2, "fat": 11.0, "fiber": 0.0, "portion": "2 ovos (100g)"},
    "leite_int": {"name": "Leite Integral", "category": "cafe_manha", "calories": 61, "protein": 3.2, "carbs": 4.7, "fat": 3.5, "fiber": 0.0, "portion": "100ml"},
    "leite_des": {"name": "Leite Desnatado", "category": "cafe_manha", "calories": 35, "protein": 3.5, "carbs": 5.0, "fat": 0.1, "fiber": 0.0, "portion": "100ml"},
    "leite_semi": {"name": "Leite Semidesnatado", "category": "cafe_manha", "calories": 46, "protein": 3.3, "carbs": 4.8, "fat": 1.5, "fiber": 0.0, "portion": "100ml"},
    "cafe_leite": {"name": "Café com Leite", "category": "cafe_manha", "calories": 50, "protein": 2.0, "carbs": 5.0, "fat": 2.0, "fiber": 0.0, "portion": "200ml"},
    "cafe_puro": {"name": "Café Preto sem Açúcar", "category": "cafe_manha", "calories": 2, "protein": 0.3, "carbs": 0.0, "fat": 0.0, "fiber": 0.0, "portion": "100ml"},
    "iog_natural": {"name": "Iogurte Natural Integral", "category": "cafe_manha", "calories": 61, "protein": 3.5, "carbs": 4.7, "fat": 3.3, "fiber": 0.0, "portion": "100g"},
    "iog_des": {"name": "Iogurte Natural Desnatado", "category": "cafe_manha", "calories": 40, "protein": 4.0, "carbs": 5.5, "fat": 0.2, "fiber": 0.0, "portion": "100g"},
    "iog_grego": {"name": "Iogurte Grego Integral", "category": "cafe_manha", "calories": 115, "protein": 8.5, "carbs": 4.0, "fat": 6.5, "fiber": 0.0, "portion": "100g"},
    "iog_grego_des": {"name": "Iogurte Grego Desnatado", "category": "cafe_manha", "calories": 59, "protein": 10.0, "carbs": 3.6, "fat": 0.4, "fiber": 0.0, "portion": "100g"},
    "aveia_flocos": {"name": "Aveia em Flocos", "category": "cafe_manha", "calories": 360, "protein": 13.0, "carbs": 64.0, "fat": 6.9, "fiber": 9.4, "portion": "100g (4 col. sopa)"},
    "mingau_aveia": {"name": "Mingau de Aveia com Leite", "category": "cafe_manha", "calories": 120, "protein": 4.5, "carbs": 18.0, "fat": 3.0, "fiber": 2.0, "portion": "200ml"},
    "granola": {"name": "Granola sem Açúcar", "category": "cafe_manha", "calories": 410, "protein": 9.0, "carbs": 60.0, "fat": 13.0, "fiber": 6.0, "portion": "100g (6 col. sopa)"},
    "mamao": {"name": "Mamão Papaia", "category": "cafe_manha", "calories": 45, "protein": 0.5, "carbs": 11.8, "fat": 0.1, "fiber": 1.8, "portion": "1 fatia (120g)"},
    "queijo_minas": {"name": "Queijo Minas Frescal", "category": "cafe_manha", "calories": 264, "protein": 17.4, "carbs": 3.5, "fat": 20.2, "fiber": 0.0, "portion": "100g (2 fatias)"},
    "queijo_cottage": {"name": "Queijo Cottage", "category": "cafe_manha", "calories": 98, "protein": 11.0, "carbs": 3.4, "fat": 4.5, "fiber": 0.0, "portion": "100g"},
    "queijo_ricota": {"name": "Ricota Fresca", "category": "cafe_manha", "calories": 174, "protein": 11.0, "carbs": 3.0, "fat": 13.0, "fiber": 0.0, "portion": "100g"},
    "manteiga": {"name": "Manteiga", "category": "cafe_manha", "calories": 717, "protein": 0.9, "carbs": 0.1, "fat": 80.5, "fiber": 0.0, "portion": "100g (1 col. chá = 5g = 36 kcal)"},
    "requeijao": {"name": "Requeijão Cremoso", "category": "cafe_manha", "calories": 227, "protein": 7.0, "carbs": 3.5, "fat": 21.0, "fiber": 0.0, "portion": "100g (1 col. sopa = 22g)"},
    # ════════════════════════════════════════════════════════════════════════
    # ALMOÇO / JANTAR — PROTEÍNAS
    # ════════════════════════════════════════════════════════════════════════
    "frango_grelhado": {"name": "Peito de Frango Grelhado", "category": "almoco", "calories": 159, "protein": 31.5, "carbs": 0.0, "fat": 3.2, "fiber": 0.0, "portion": "100g"},
    "frango_cozido": {"name": "Peito de Frango Cozido", "category": "almoco", "calories": 163, "protein": 31.5, "carbs": 0.0, "fat": 3.6, "fiber": 0.0, "portion": "100g"},
    "coxa_frango": {"name": "Coxa de Frango Assada (sem pele)", "category": "almoco", "calories": 178, "protein": 26.0, "carbs": 0.0, "fat": 7.7, "fiber": 0.0, "portion": "100g"},
    "sobrecoxa": {"name": "Sobrecoxa Frango Cozida", "category": "almoco", "calories": 192, "protein": 24.5, "carbs": 0.0, "fat": 10.0, "fiber": 0.0, "portion": "100g"},
    "frango_assado": {"name": "Frango Assado Inteiro (sem pele)", "category": "almoco", "calories": 170, "protein": 29.2, "carbs": 0.0, "fat": 5.3, "fiber": 0.0, "portion": "100g"},
    "alcatra": {"name": "Alcatra Grelhada", "category": "almoco", "calories": 196, "protein": 29.0, "carbs": 0.0, "fat": 8.3, "fiber": 0.0, "portion": "100g"},
    "contrafile": {"name": "Contrafilé Bovino Grelhado", "category": "almoco", "calories": 219, "protein": 27.0, "carbs": 0.0, "fat": 12.0, "fiber": 0.0, "portion": "100g"},
    "carne_moida": {"name": "Carne Moída Patinho Refogada", "category": "almoco", "calories": 189, "protein": 26.0, "carbs": 0.0, "fat": 9.0, "fiber": 0.0, "portion": "100g"},
    "patinho": {"name": "Patinho Bovino Cozido", "category": "almoco", "calories": 183, "protein": 28.8, "carbs": 0.0, "fat": 6.5, "fiber": 0.0, "portion": "100g"},
    "picanha": {"name": "Picanha Grelhada", "category": "almoco", "calories": 260, "protein": 26.5, "carbs": 0.0, "fat": 16.8, "fiber": 0.0, "portion": "100g"},
    "costela": {"name": "Costela Bovina Assada", "category": "almoco", "calories": 235, "protein": 20.5, "carbs": 0.0, "fat": 16.0, "fiber": 0.0, "portion": "100g"},
    "figado_bovino": {"name": "Fígado Bovino Grelhado", "category": "almoco", "calories": 175, "protein": 26.5, "carbs": 4.0, "fat": 5.0, "fiber": 0.0, "portion": "100g"},
    "tilapia": {"name": "Tilápia Grelhada", "category": "almoco", "calories": 128, "protein": 26.2, "carbs": 0.0, "fat": 2.3, "fiber": 0.0, "portion": "100g"},
    "salmao": {"name": "Salmão Grelhado", "category": "almoco", "calories": 208, "protein": 28.0, "carbs": 0.0, "fat": 10.5, "fiber": 0.0, "portion": "100g"},
    "atum_grelh": {"name": "Atum Fresco Grelhado", "category": "almoco", "calories": 144, "protein": 29.5, "carbs": 0.0, "fat": 3.0, "fiber": 0.0, "portion": "100g"},
    "atum_latinha": {"name": "Atum em Lata (água, escorrido)", "category": "almoco", "calories": 128, "protein": 29.0, "carbs": 0.0, "fat": 1.0, "fiber": 0.0, "portion": "100g"},
    "sardinha": {"name": "Sardinha em Lata (óleo, escorrida)", "category": "almoco", "calories": 208, "protein": 24.6, "carbs": 0.0, "fat": 11.5, "fiber": 0.0, "portion": "100g"},
    "camarao": {"name": "Camarão Cozido", "category": "almoco", "calories": 99, "protein": 21.0, "carbs": 0.9, "fat": 1.1, "fiber": 0.0, "portion": "100g"},
    "bacalhau": {"name": "Bacalhau Cozido (dessalgado)", "category": "almoco", "calories": 141, "protein": 32.5, "carbs": 0.0, "fat": 0.6, "fiber": 0.0, "portion": "100g"},
    "carne_porco": {"name": "Lombo de Porco Assado", "category": "almoco", "calories": 197, "protein": 28.0, "carbs": 0.0, "fat": 9.3, "fiber": 0.0, "portion": "100g"},
    "frango_desfiado": {"name": "Frango Desfiado Cozido", "category": "almoco", "calories": 149, "protein": 28.5, "carbs": 0.0, "fat": 3.5, "fiber": 0.0, "portion": "100g"},
    "whey": {"name": "Whey Protein (1 dose)", "category": "pre_pos_treino", "calories": 120, "protein": 24.0, "carbs": 3.0, "fat": 2.0, "fiber": 0.0, "portion": "30g"},
    # ════════════════════════════════════════════════════════════════════════
    # ALMOÇO / JANTAR — CARBOIDRATOS
    # ════════════════════════════════════════════════════════════════════════
    "arroz_branco": {"name": "Arroz Branco Cozido", "category": "almoco", "calories": 128, "protein": 2.5, "carbs": 28.0, "fat": 0.2, "fiber": 0.2, "portion": "100g (4 col. sopa)"},
    "arroz_integral": {"name": "Arroz Integral Cozido", "category": "almoco", "calories": 124, "protein": 2.8, "carbs": 26.0, "fat": 0.8, "fiber": 1.7, "portion": "100g (4 col. sopa)"},
    "arroz_parboil": {"name": "Arroz Parboilizado Cozido", "category": "almoco", "calories": 131, "protein": 2.6, "carbs": 28.5, "fat": 0.3, "fiber": 0.5, "portion": "100g"},
    "feijao_carioca": {"name": "Feijão Carioca Cozido", "category": "almoco", "calories": 76, "protein": 4.8, "carbs": 13.6, "fat": 0.5, "fiber": 6.4, "portion": "100g (1 concha)"},
    "feijao_preto": {"name": "Feijão Preto Cozido", "category": "almoco", "calories": 77, "protein": 4.5, "carbs": 14.0, "fat": 0.5, "fiber": 6.3, "portion": "100g (1 concha)"},
    "feijao_branco": {"name": "Feijão Branco Cozido", "category": "almoco", "calories": 139, "protein": 9.1, "carbs": 25.1, "fat": 0.5, "fiber": 7.4, "portion": "100g"},
    "lentilha": {"name": "Lentilha Cozida", "category": "almoco", "calories": 93, "protein": 7.7, "carbs": 15.2, "fat": 0.5, "fiber": 4.0, "portion": "100g"},
    "grao_de_bico": {"name": "Grão-de-Bico Cozido", "category": "almoco", "calories": 160, "protein": 8.9, "carbs": 27.4, "fat": 2.6, "fiber": 4.3, "portion": "100g"},
    "ervilha_coz": {"name": "Ervilha Cozida", "category": "almoco", "calories": 87, "protein": 6.4, "carbs": 15.5, "fat": 0.4, "fiber": 4.5, "portion": "100g"},
    "quinoa": {"name": "Quinoa Cozida", "category": "almoco", "calories": 120, "protein": 4.4, "carbs": 21.3, "fat": 1.9, "fiber": 2.8, "portion": "100g"},
    "batata_ing": {"name": "Batata Inglesa Cozida", "category": "almoco", "calories": 52, "protein": 1.2, "carbs": 11.9, "fat": 0.1, "fiber": 1.0, "portion": "100g"},
    "batata_doce_coz": {"name": "Batata-Doce Cozida", "category": "almoco", "calories": 77, "protein": 0.6, "carbs": 18.4, "fat": 0.1, "fiber": 2.5, "portion": "100g"},
    "batata_doce_ass": {"name": "Batata-Doce Assada", "category": "almoco", "calories": 90, "protein": 2.0, "carbs": 20.7, "fat": 0.1, "fiber": 3.0, "portion": "100g"},
    "inhame": {"name": "Inhame Cozido", "category": "almoco", "calories": 116, "protein": 1.5, "carbs": 27.5, "fat": 0.1, "fiber": 4.1, "portion": "100g"},
    "mandioca": {"name": "Mandioca Cozida", "category": "almoco", "calories": 135, "protein": 0.6, "carbs": 32.9, "fat": 0.3, "fiber": 1.9, "portion": "100g"},
    "macarrao_esp": {"name": "Espaguete Grano Duro Cozido", "category": "almoco", "calories": 131, "protein": 4.9, "carbs": 26.4, "fat": 0.9, "fiber": 1.8, "portion": "100g"},
    "macarrao_int": {"name": "Macarrão Integral Cozido", "category": "almoco", "calories": 124, "protein": 5.3, "carbs": 26.0, "fat": 0.5, "fiber": 3.5, "portion": "100g"},
    "polenta": {"name": "Polenta Cozida (fubá)", "category": "almoco", "calories": 86, "protein": 2.0, "carbs": 17.5, "fat": 0.5, "fiber": 0.7, "portion": "100g"},
    # ════════════════════════════════════════════════════════════════════════
    # ALMOÇO / JANTAR — VEGETAIS E LEGUMES
    # ════════════════════════════════════════════════════════════════════════
    "brocolis": {"name": "Brócolis Cozido", "category": "almoco", "calories": 25, "protein": 2.9, "carbs": 3.7, "fat": 0.4, "fiber": 2.6, "portion": "100g"},
    "couve_ref": {"name": "Couve Refogada com Alho", "category": "almoco", "calories": 44, "protein": 3.0, "carbs": 5.6, "fat": 1.6, "fiber": 2.0, "portion": "100g"},
    "espinafre": {"name": "Espinafre Cozido", "category": "almoco", "calories": 23, "protein": 2.7, "carbs": 3.5, "fat": 0.3, "fiber": 2.2, "portion": "100g"},
    "cenoura_coz": {"name": "Cenoura Cozida", "category": "almoco", "calories": 35, "protein": 0.9, "carbs": 8.2, "fat": 0.2, "fiber": 3.0, "portion": "100g"},
    "cenoura_crua": {"name": "Cenoura Crua", "category": "almoco", "calories": 34, "protein": 0.6, "carbs": 7.7, "fat": 0.3, "fiber": 3.2, "portion": "100g"},
    "abobrinha": {"name": "Abobrinha Refogada", "category": "almoco", "calories": 18, "protein": 1.2, "carbs": 3.1, "fat": 0.3, "fiber": 1.1, "portion": "100g"},
    "chuchu": {"name": "Chuchu Cozido", "category": "almoco", "calories": 22, "protein": 0.9, "carbs": 5.1, "fat": 0.1, "fiber": 1.6, "portion": "100g"},
    "beterraba": {"name": "Beterraba Cozida", "category": "almoco", "calories": 43, "protein": 1.7, "carbs": 9.6, "fat": 0.1, "fiber": 2.8, "portion": "100g"},
    "tomate": {"name": "Tomate Cru", "category": "almoco", "calories": 18, "protein": 0.9, "carbs": 3.9, "fat": 0.2, "fiber": 1.2, "portion": "100g"},
    "pepino": {"name": "Pepino Cru", "category": "almoco", "calories": 13, "protein": 0.6, "carbs": 2.9, "fat": 0.1, "fiber": 0.5, "portion": "100g"},
    "alface": {"name": "Alface Cru", "category": "almoco", "calories": 11, "protein": 1.3, "carbs": 1.7, "fat": 0.2, "fiber": 1.5, "portion": "100g"},
    "rucula": {"name": "Rúcula Crua", "category": "almoco", "calories": 25, "protein": 2.6, "carbs": 3.7, "fat": 0.7, "fiber": 1.6, "portion": "100g"},
    "repolho": {"name": "Repolho Cozido", "category": "almoco", "calories": 22, "protein": 1.1, "carbs": 4.8, "fat": 0.1, "fiber": 2.3, "portion": "100g"},
    "cebola": {"name": "Cebola Crua", "category": "almoco", "calories": 40, "protein": 1.1, "carbs": 9.3, "fat": 0.1, "fiber": 1.7, "portion": "100g"},
    "alho": {"name": "Alho Cru", "category": "almoco", "calories": 149, "protein": 6.4, "carbs": 33.1, "fat": 0.5, "fiber": 2.1, "portion": "100g (1 dente = 3g = 4 kcal)"},
    "cogumelo": {"name": "Cogumelo Champignon Cozido", "category": "almoco", "calories": 28, "protein": 2.2, "carbs": 5.1, "fat": 0.3, "fiber": 1.1, "portion": "100g"},
    "quiabo": {"name": "Quiabo Cozido", "category": "almoco", "calories": 30, "protein": 1.9, "carbs": 6.0, "fat": 0.1, "fiber": 3.2, "portion": "100g"},
    "vagem": {"name": "Vagem Cozida", "category": "almoco", "calories": 31, "protein": 2.0, "carbs": 6.1, "fat": 0.2, "fiber": 3.4, "portion": "100g"},
    "pimentao": {"name": "Pimentão (amarelo/vermelho)", "category": "almoco", "calories": 27, "protein": 1.0, "carbs": 6.3, "fat": 0.3, "fiber": 2.1, "portion": "100g"},
    "milho_coz": {"name": "Milho Verde Cozido", "category": "almoco", "calories": 76, "protein": 2.8, "carbs": 15.5, "fat": 1.0, "fiber": 2.1, "portion": "100g"},
    # ════════════════════════════════════════════════════════════════════════
    # LANCHES E FRUTAS
    # ════════════════════════════════════════════════════════════════════════
    "banana_prata": {"name": "Banana Prata", "category": "lanche", "calories": 98, "protein": 1.3, "carbs": 26.0, "fat": 0.1, "fiber": 2.0, "portion": "1 unidade (90g)"},
    "banana_nanica": {"name": "Banana Nanica", "category": "lanche", "calories": 92, "protein": 1.4, "carbs": 23.8, "fat": 0.1, "fiber": 1.9, "portion": "1 unidade (85g)"},
    "maca": {"name": "Maçã Fuji com Casca", "category": "lanche", "calories": 55, "protein": 0.3, "carbs": 14.0, "fat": 0.2, "fiber": 2.0, "portion": "1 unidade (100g)"},
    "pera": {"name": "Pera Williams", "category": "lanche", "calories": 53, "protein": 0.4, "carbs": 13.9, "fat": 0.1, "fiber": 3.1, "portion": "1 unidade (100g)"},
    "laranja": {"name": "Laranja Pêra", "category": "lanche", "calories": 46, "protein": 0.9, "carbs": 11.5, "fat": 0.1, "fiber": 0.8, "portion": "1 unidade (130g)"},
    "morango": {"name": "Morango", "category": "lanche", "calories": 32, "protein": 0.7, "carbs": 7.7, "fat": 0.3, "fiber": 2.0, "portion": "100g (8 unidades)"},
    "melancia": {"name": "Melancia", "category": "lanche", "calories": 29, "protein": 0.6, "carbs": 7.6, "fat": 0.1, "fiber": 0.4, "portion": "1 fatia (200g)"},
    "melao": {"name": "Melão Amarelo", "category": "lanche", "calories": 29, "protein": 0.7, "carbs": 6.9, "fat": 0.1, "fiber": 0.3, "portion": "1 fatia (150g)"},
    "manga": {"name": "Manga Tommy", "category": "lanche", "calories": 64, "protein": 0.8, "carbs": 16.8, "fat": 0.3, "fiber": 1.6, "portion": "1/2 manga (130g)"},
    "mamao_l": {"name": "Mamão Papaia", "category": "lanche", "calories": 45, "protein": 0.5, "carbs": 11.8, "fat": 0.1, "fiber": 1.8, "portion": "1 fatia (150g)"},
    "abacaxi": {"name": "Abacaxi", "category": "lanche", "calories": 48, "protein": 0.5, "carbs": 12.3, "fat": 0.1, "fiber": 1.0, "portion": "1 fatia (100g)"},
    "uva": {"name": "Uva Comum", "category": "lanche", "calories": 69, "protein": 0.6, "carbs": 17.7, "fat": 0.4, "fiber": 0.9, "portion": "1 cacho (100g)"},
    "goiaba": {"name": "Goiaba Vermelha", "category": "lanche", "calories": 54, "protein": 2.6, "carbs": 12.0, "fat": 0.5, "fiber": 6.2, "portion": "1 unidade (100g)"},
    "kiwi": {"name": "Kiwi", "category": "lanche", "calories": 61, "protein": 1.1, "carbs": 14.7, "fat": 0.5, "fiber": 3.0, "portion": "1 unidade (80g)"},
    "abacate": {"name": "Abacate", "category": "lanche", "calories": 160, "protein": 2.0, "carbs": 9.0, "fat": 15.0, "fiber": 6.7, "portion": "1/4 unidade (50g)"},
    "coco_fresco": {"name": "Coco Verde (polpa)", "category": "lanche", "calories": 159, "protein": 1.5, "carbs": 6.9, "fat": 15.1, "fiber": 4.5, "portion": "100g"},
    "amendoim": {"name": "Amendoim Torrado sem Sal", "category": "lanche", "calories": 567, "protein": 25.8, "carbs": 18.0, "fat": 47.5, "fiber": 8.0, "portion": "100g (3 col. sopa = 30g = 170 kcal)"},
    "castanha_para": {"name": "Castanha-do-Pará", "category": "lanche", "calories": 656, "protein": 14.3, "carbs": 12.3, "fat": 63.5, "fiber": 7.5, "portion": "100g (6 unidades = 30g = 197 kcal)"},
    "castanha_caju": {"name": "Castanha de Caju Torrada sem Sal", "category": "lanche", "calories": 570, "protein": 18.5, "carbs": 29.0, "fat": 46.3, "fiber": 3.7, "portion": "100g"},
    "noz": {"name": "Nozes", "category": "lanche", "calories": 620, "protein": 14.3, "carbs": 13.7, "fat": 59.4, "fiber": 6.7, "portion": "100g (4 unidades = 30g = 186 kcal)"},
    "amendoas": {"name": "Amêndoas sem Sal", "category": "lanche", "calories": 575, "protein": 21.2, "carbs": 19.6, "fat": 49.4, "fiber": 12.5, "portion": "100g (20 unidades = 28g = 161 kcal)"},
    "pasta_amendoim": {"name": "Pasta de Amendoim Integral", "category": "lanche", "calories": 600, "protein": 25.0, "carbs": 20.0, "fat": 50.0, "fiber": 6.0, "portion": "100g (1 col. sopa = 16g = 96 kcal)"},
    # ════════════════════════════════════════════════════════════════════════
    # PRÉ E PÓS-TREINO
    # ════════════════════════════════════════════════════════════════════════
    "banana_oleo": {"name": "Banana com Pasta de Amendoim", "category": "pre_pos_treino", "calories": 218, "protein": 6.0, "carbs": 33.0, "fat": 8.5, "fiber": 3.5, "portion": "1 banana + 1 col. sopa pasta (130g)"},
    "creatina": {"name": "Creatina Monoidratada", "category": "pre_pos_treino", "calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0, "portion": "5g (1 dose)"},
    "bcaa": {"name": "BCAA (aminoácidos ramificados)", "category": "pre_pos_treino", "calories": 20, "protein": 5.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0, "portion": "5g (1 dose)"},
    "barra_prot": {"name": "Barra de Proteína (média)", "category": "pre_pos_treino", "calories": 190, "protein": 20.0, "carbs": 22.0, "fat": 5.0, "fiber": 3.0, "portion": "1 unidade (55g)"},
    "barra_cereal": {"name": "Barra de Cereal", "category": "pre_pos_treino", "calories": 128, "protein": 1.8, "carbs": 25.0, "fat": 3.0, "fiber": 1.2, "portion": "1 unidade (32g)"},
    "isoton": {"name": "Isotônico (Gatorade/similar)", "category": "pre_pos_treino", "calories": 28, "protein": 0.0, "carbs": 7.0, "fat": 0.0, "fiber": 0.0, "portion": "100ml"},
    "whey_choc": {"name": "Whey Protein Concentrado (chocolate)", "category": "pre_pos_treino", "calories": 120, "protein": 24.0, "carbs": 5.0, "fat": 2.0, "fiber": 0.0, "portion": "30g (1 dose)"},
    "frango_batata": {"name": "Frango Grelhado + Batata-Doce", "category": "pre_pos_treino", "calories": 236, "protein": 31.5, "carbs": 18.4, "fat": 3.3, "fiber": 2.5, "portion": "100g frango + 100g batata"},
    # ════════════════════════════════════════════════════════════════════════
    # GORDURAS SAUDÁVEIS
    # ════════════════════════════════════════════════════════════════════════
    "azeite": {"name": "Azeite de Oliva Extra Virgem", "category": "almoco", "calories": 884, "protein": 0.0, "carbs": 0.0, "fat": 100.0, "fiber": 0.0, "portion": "100ml (1 col. sopa = 14ml = 124 kcal)"},
    "oleo_coco": {"name": "Óleo de Coco", "category": "cafe_manha", "calories": 892, "protein": 0.0, "carbs": 0.0, "fat": 100.0, "fiber": 0.0, "portion": "100ml (1 col. sopa = 13ml = 116 kcal)"},
    "oleo_milho": {"name": "Óleo de Milho/Soja", "category": "almoco", "calories": 900, "protein": 0.0, "carbs": 0.0, "fat": 100.0, "fiber": 0.0, "portion": "100ml (1 col. sopa = 14ml = 126 kcal)"},
    # ════════════════════════════════════════════════════════════════════════
    # REFEIÇÕES PRONTAS / PRATOS TÍPICOS BRASILEIROS
    # ════════════════════════════════════════════════════════════════════════
    "arroz_feijao": {"name": "Arroz + Feijão (prato base)", "category": "almoco", "calories": 183, "protein": 6.4, "carbs": 36.0, "fat": 1.3, "fiber": 3.6, "portion": "200g (1 prato)"},
    "prato_completo": {"name": "Prato Completo (arroz+feijão+frango+salada)", "category": "almoco", "calories": 478, "protein": 39.0, "carbs": 45.0, "fat": 10.0, "fiber": 5.5, "portion": "350g (1 prato)"},
    "frango_legumes": {"name": "Frango Grelhado com Legumes no Vapor", "category": "almoco", "calories": 212, "protein": 33.0, "carbs": 10.0, "fat": 4.5, "fiber": 3.5, "portion": "250g"},
    "omelete_legumes": {"name": "Omelete de 2 Ovos com Legumes", "category": "almoco", "calories": 195, "protein": 14.5, "carbs": 6.0, "fat": 12.5, "fiber": 2.0, "portion": "200g"},
    "sopa_legumes": {"name": "Sopa de Legumes com Frango", "category": "jantar", "calories": 85, "protein": 7.0, "carbs": 9.0, "fat": 2.0, "fiber": 2.5, "portion": "300ml (1 prato)"},
    "salada_completa": {"name": "Salada Mista Completa (folhas+legumes)", "category": "almoco", "calories": 55, "protein": 2.5, "carbs": 8.5, "fat": 1.5, "fiber": 3.5, "portion": "200g"},
    "sushi_hossomaki": {"name": "Hossomaki (salmão, 1 peça)", "category": "almoco", "calories": 30, "protein": 1.5, "carbs": 4.5, "fat": 0.5, "fiber": 0.2, "portion": "25g (1 peça)"},
    "pizza_fatia": {"name": "Pizza Mussarela (1 fatia)", "category": "jantar", "calories": 266, "protein": 11.5, "carbs": 30.0, "fat": 11.5, "fiber": 1.5, "portion": "1 fatia (100g)"},
    "hamburguer": {"name": "Hambúrguer Artesanal (sem pão)", "category": "almoco", "calories": 245, "protein": 22.0, "carbs": 3.0, "fat": 16.5, "fiber": 0.0, "portion": "150g"},
    # ════════════════════════════════════════════════════════════════════════
    # BEBIDAS
    # ════════════════════════════════════════════════════════════════════════
    "agua_coco": {"name": "Água de Coco Natural", "category": "lanche", "calories": 19, "protein": 0.2, "carbs": 3.7, "fat": 0.2, "fiber": 0.0, "portion": "100ml"},
    "suco_laranja": {"name": "Suco de Laranja Natural", "category": "cafe_manha", "calories": 45, "protein": 0.7, "carbs": 10.4, "fat": 0.2, "fiber": 0.2, "portion": "200ml"},
    "suco_maracuja": {"name": "Suco de Maracujá Natural sem Açúcar", "category": "lanche", "calories": 25, "protein": 0.7, "carbs": 5.5, "fat": 0.2, "fiber": 0.4, "portion": "200ml"},
    "vitamina_banana": {"name": "Vitamina de Banana com Leite", "category": "cafe_manha", "calories": 139, "protein": 4.0, "carbs": 25.0, "fat": 2.8, "fiber": 1.5, "portion": "300ml"},
    "cha_verde": {"name": "Chá Verde sem Açúcar", "category": "lanche", "calories": 1, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0, "portion": "200ml"},
    "cha_camomila": {"name": "Chá de Camomila", "category": "ceia", "calories": 2, "protein": 0.0, "carbs": 0.5, "fat": 0.0, "fiber": 0.0, "portion": "200ml"},
    "leite_quente_mel": {"name": "Leite Quente com Mel", "category": "ceia", "calories": 90, "protein": 3.2, "carbs": 13.0, "fat": 3.5, "fiber": 0.0, "portion": "200ml"},
    # ════════════════════════════════════════════════════════════════════════
    # LATICÍNIOS COMPLEMENTARES
    # ════════════════════════════════════════════════════════════════════════
    "queijo_prato": {"name": "Queijo Prato", "category": "cafe_manha", "calories": 358, "protein": 24.0, "carbs": 2.2, "fat": 28.0, "fiber": 0.0, "portion": "100g (1 fatia = 20g = 72 kcal)"},
    "queijo_mussarela": {"name": "Queijo Mussarela", "category": "cafe_manha", "calories": 300, "protein": 22.0, "carbs": 2.0, "fat": 22.5, "fiber": 0.0, "portion": "100g (1 fatia = 25g = 75 kcal)"},
    "queijo_minas_cur": {"name": "Queijo Minas Curado", "category": "cafe_manha", "calories": 346, "protein": 24.5, "carbs": 2.5, "fat": 26.5, "fiber": 0.0, "portion": "100g"},
    "leite_condensado": {"name": "Leite Condensado", "category": "outro", "calories": 321, "protein": 7.8, "carbs": 55.0, "fat": 8.0, "fiber": 0.0, "portion": "100g"},
    # ════════════════════════════════════════════════════════════════════════
    # SUPLEMENTOS E COMPOSTOS
    # ════════════════════════════════════════════════════════════════════════
    "oleo_peixe": {"name": "Ômega-3 (cápsula)", "category": "pre_pos_treino", "calories": 9, "protein": 0.0, "carbs": 0.0, "fat": 1.0, "fiber": 0.0, "portion": "1 cápsula de 1g"},
    "albumina": {"name": "Albumina em Pó", "category": "pre_pos_treino", "calories": 88, "protein": 22.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0, "portion": "25g (1 dose)"},
    "colageno": {"name": "Colágeno Hidrolisado em Pó", "category": "pre_pos_treino", "calories": 90, "protein": 22.0, "carbs": 0.0, "fat": 0.3, "fiber": 0.0, "portion": "25g"},
    # ════════════════════════════════════════════════════════════════════════
    # OUTROS / CONDIMENTOS
    # ════════════════════════════════════════════════════════════════════════
    "mel": {"name": "Mel Puro", "category": "cafe_manha", "calories": 309, "protein": 0.3, "carbs": 84.0, "fat": 0.0, "fiber": 0.2, "portion": "100g (1 col. sopa = 21g = 65 kcal)"},
    "acucar_cristal": {"name": "Açúcar Cristal", "category": "outro", "calories": 400, "protein": 0.0, "carbs": 99.9, "fat": 0.0, "fiber": 0.0, "portion": "100g (1 col. chá = 4g = 16 kcal)"},
    "adocante": {"name": "Adoçante Stevia", "category": "outro", "calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0, "portion": "1 sachê"},
    "ketchup": {"name": "Ketchup", "category": "outro", "calories": 101, "protein": 1.5, "carbs": 25.0, "fat": 0.4, "fiber": 0.8, "portion": "100g"},
    "maionese": {"name": "Maionese Tradicional", "category": "outro", "calories": 680, "protein": 1.0, "carbs": 2.5, "fat": 75.0, "fiber": 0.0, "portion": "100g (1 col. sopa = 14g = 95 kcal)"},
    "maionese_light": {"name": "Maionese Light", "category": "outro", "calories": 265, "protein": 1.2, "carbs": 12.0, "fat": 23.0, "fiber": 0.0, "portion": "100g"},
    "molho_tomate": {"name": "Molho de Tomate Caseiro", "category": "almoco", "calories": 36, "protein": 1.5, "carbs": 7.5, "fat": 0.3, "fiber": 1.5, "portion": "100g"},
    # ════════════════════════════════════════════════════════════════════════
    # SUPLEMENTOS BARIÁTRICOS / GLP-1 (essenciais para os pilares)
    # ════════════════════════════════════════════════════════════════════════
    "vit_d3": {"name": "Vitamina D3 (suplemento)", "category": "pre_pos_treino", "calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0, "portion": "1 cápsula"},
    "vit_b12": {"name": "Vitamina B12 (suplemento)", "category": "pre_pos_treino", "calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0, "portion": "1 cápsula"},
    "calcio_citrato": {"name": "Cálcio Citrato (suplemento)", "category": "pre_pos_treino", "calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0, "portion": "1 comprimido"},
    "ferro_quelado": {"name": "Ferro Quelado (suplemento)", "category": "pre_pos_treino", "calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0, "portion": "1 cápsula"},
    "zinco": {"name": "Zinco Quelado (suplemento)", "category": "pre_pos_treino", "calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0, "portion": "1 cápsula"},
    "magnesio": {"name": "Magnésio Quelado (suplemento)", "category": "pre_pos_treino", "calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0, "portion": "1 cápsula"},
    # ════════════════════════════════════════════════════════════════════════
    # PROTEÍNAS VEGETAIS (fitness + emagrecimento)
    # ════════════════════════════════════════════════════════════════════════
    "tofu_firm": {"name": "Tofu Firme Grelhado", "category": "almoco", "calories": 144, "protein": 17.3, "carbs": 2.8, "fat": 8.7, "fiber": 0.3, "portion": "100g"},
    "edamame": {"name": "Edamame (soja verde) Cozido", "category": "lanche", "calories": 121, "protein": 11.9, "carbs": 8.9, "fat": 5.2, "fiber": 5.2, "portion": "100g"},
    "proteina_soja": {"name": "Proteína Texturizada de Soja (PTS)", "category": "almoco", "calories": 330, "protein": 52.0, "carbs": 29.0, "fat": 1.0, "fiber": 16.0, "portion": "100g seca (hidratada = 300g)"},
    "grao_bico_ref": {"name": "Grão-de-Bico Refogado com Azeite", "category": "almoco", "calories": 185, "protein": 9.5, "carbs": 27.0, "fat": 5.0, "fiber": 4.5, "portion": "150g"},
    # ════════════════════════════════════════════════════════════════════════
    # CEREAIS MATINAIS / FIBRAS
    # ════════════════════════════════════════════════════════════════════════
    "farelo_aveia": {"name": "Farelo de Aveia", "category": "cafe_manha", "calories": 246, "protein": 17.3, "carbs": 58.0, "fat": 7.0, "fiber": 15.4, "portion": "100g (2 col. sopa = 20g = 49 kcal)"},
    "chia": {"name": "Semente de Chia", "category": "cafe_manha", "calories": 486, "protein": 16.5, "carbs": 42.1, "fat": 30.7, "fiber": 34.4, "portion": "100g (1 col. sopa = 12g = 58 kcal)"},
    "linhaça_dour": {"name": "Semente de Linhaça Dourada", "category": "cafe_manha", "calories": 495, "protein": 18.3, "carbs": 28.9, "fat": 42.2, "fiber": 27.3, "portion": "100g (1 col. sopa = 12g = 59 kcal)"},
    "germen_trigo": {"name": "Gérmen de Trigo", "category": "cafe_manha", "calories": 360, "protein": 26.6, "carbs": 51.8, "fat": 9.7, "fiber": 13.2, "portion": "100g (1 col. sopa = 10g = 36 kcal)"},
    "cereal_milho": {"name": "Flocos de Milho (corn flakes)", "category": "cafe_manha", "calories": 374, "protein": 7.5, "carbs": 84.0, "fat": 0.5, "fiber": 2.0, "portion": "100g (1 tigela = 40g = 150 kcal)"},
    # ════════════════════════════════════════════════════════════════════════
    # CEIA / JANTAR LEVE
    # ════════════════════════════════════════════════════════════════════════
    "creme_ricota": {"name": "Creme de Ricota com Ervas", "category": "ceia", "calories": 140, "protein": 9.0, "carbs": 4.0, "fat": 10.0, "fiber": 0.0, "portion": "100g"},
    "iog_ceia": {"name": "Iogurte Grego com Mel e Nozes", "category": "ceia", "calories": 175, "protein": 9.0, "carbs": 14.0, "fat": 9.0, "fiber": 0.5, "portion": "150g"},
    "fruta_ceia": {"name": "Maçã Assada com Canela", "category": "ceia", "calories": 72, "protein": 0.4, "carbs": 19.0, "fat": 0.3, "fiber": 2.5, "portion": "1 unidade (130g)"},
    "ovo_cozido_ceia": {"name": "Ovo Cozido (ceia proteica)", "category": "ceia", "calories": 77, "protein": 6.5, "carbs": 0.6, "fat": 5.3, "fiber": 0.0, "portion": "1 unidade (50g)"},
    "cottage_frutas": {"name": "Cottage com Frutas Vermelhas", "category": "ceia", "calories": 120, "protein": 12.0, "carbs": 10.0, "fat": 3.5, "fiber": 1.5, "portion": "150g"},
    # ════════════════════════════════════════════════════════════════════════
    # PROTEÍNAS ANIMAIS COMPLEMENTARES
    # ════════════════════════════════════════════════════════════════════════
    "linguica_frango": {"name": "Linguiça de Frango Grelhada", "category": "almoco", "calories": 205, "protein": 17.0, "carbs": 2.5, "fat": 14.5, "fiber": 0.0, "portion": "100g"},
    "peito_peru": {"name": "Peito de Peru Fatiado (light)", "category": "almoco", "calories": 109, "protein": 22.0, "carbs": 1.5, "fat": 1.5, "fiber": 0.0, "portion": "100g (4 fatias)"},
    "presunto_cozido": {"name": "Presunto Cozido", "category": "cafe_manha", "calories": 120, "protein": 17.5, "carbs": 2.0, "fat": 4.5, "fiber": 0.0, "portion": "100g (4 fatias)"},
    "atum_premium": {"name": "Atum em Lata (óleo de oliva)", "category": "almoco", "calories": 198, "protein": 27.0, "carbs": 0.0, "fat": 10.0, "fiber": 0.0, "portion": "100g"},
    "peixe_branco": {"name": "Pescada Grelhada", "category": "almoco", "calories": 111, "protein": 23.5, "carbs": 0.0, "fat": 1.5, "fiber": 0.0, "portion": "100g"},
    "frango_frito": {"name": "Frango Empanado Frito", "category": "almoco", "calories": 285, "protein": 20.0, "carbs": 15.0, "fat": 16.0, "fiber": 0.5, "portion": "100g"},
    # ════════════════════════════════════════════════════════════════════════
    # SNACKS E LANCHES RÁPIDOS
    # ════════════════════════════════════════════════════════════════════════
    "pipoca_air": {"name": "Pipoca Sem Óleo (air popped)", "category": "lanche", "calories": 375, "protein": 11.0, "carbs": 74.0, "fat": 4.3, "fiber": 14.5, "portion": "100g (1 saco médio = 30g = 113 kcal)"},
    "torrada_int": {"name": "Torrada Integral", "category": "lanche", "calories": 347, "protein": 12.0, "carbs": 68.0, "fat": 3.5, "fiber": 6.0, "portion": "100g (2 torradas = 20g = 69 kcal)"},
    "chips_batata": {"name": "Chips de Batata (industrializado)", "category": "lanche", "calories": 536, "protein": 7.0, "carbs": 53.0, "fat": 34.0, "fiber": 3.8, "portion": "100g (1 saquinho pequeno = 35g = 188 kcal)"},
    "chocolate_amargo": {"name": "Chocolate Amargo 70%+", "category": "lanche", "calories": 558, "protein": 9.5, "carbs": 29.5, "fat": 42.0, "fiber": 10.9, "portion": "100g (1 quadrado = 10g = 56 kcal)"},
    "barrinha_castanha": {"name": "Barrinha de Castanha e Mel", "category": "lanche", "calories": 440, "protein": 9.0, "carbs": 58.0, "fat": 20.0, "fiber": 3.5, "portion": "100g (1 unidade = 25g = 110 kcal)"},
    # ════════════════════════════════════════════════════════════════════════
    # VEGETAIS COMPLEMENTARES
    # ════════════════════════════════════════════════════════════════════════
    "mandioquinha": {"name": "Mandioquinha (Batata Baroa) Cozida", "category": "almoco", "calories": 90, "protein": 2.0, "carbs": 19.5, "fat": 0.5, "fiber": 2.5, "portion": "100g"},
    "berinjela": {"name": "Berinjela Grelhada", "category": "almoco", "calories": 22, "protein": 1.0, "carbs": 5.1, "fat": 0.2, "fiber": 3.0, "portion": "100g"},
    "brocolis_nin": {"name": "Brócolis Ninja (Romanesco) Cozido", "category": "almoco", "calories": 29, "protein": 2.5, "carbs": 5.5, "fat": 0.4, "fiber": 3.5, "portion": "100g"},
    "couve_flor": {"name": "Couve-Flor Cozida", "category": "almoco", "calories": 25, "protein": 1.9, "carbs": 4.9, "fat": 0.3, "fiber": 2.0, "portion": "100g"},
    "aspargo": {"name": "Aspargo Cozido", "category": "almoco", "calories": 20, "protein": 2.2, "carbs": 3.7, "fat": 0.1, "fiber": 2.1, "portion": "100g (6 talos)"},
    # ════════════════════════════════════════════════════════════════════════
    # FRUTAS COMPLEMENTARES
    # ════════════════════════════════════════════════════════════════════════
    "acai_puro": {"name": "Açaí Puro Congelado (sem xarope)", "category": "lanche", "calories": 247, "protein": 4.5, "carbs": 6.0, "fat": 21.0, "fiber": 4.2, "portion": "100g"},
    "framboesa": {"name": "Framboesa", "category": "lanche", "calories": 52, "protein": 1.2, "carbs": 11.9, "fat": 0.7, "fiber": 6.5, "portion": "100g"},
    "mirtilos": {"name": "Mirtilo (Blueberry)", "category": "lanche", "calories": 57, "protein": 0.7, "carbs": 14.5, "fat": 0.3, "fiber": 2.4, "portion": "100g"},
    "caju": {"name": "Caju Fresco", "category": "lanche", "calories": 43, "protein": 0.9, "carbs": 10.3, "fat": 0.4, "fiber": 1.5, "portion": "100g (1 caju = 40g = 17 kcal)"},
    "tamarindo": {"name": "Tamarindo", "category": "lanche", "calories": 239, "protein": 2.8, "carbs": 62.5, "fat": 0.6, "fiber": 5.1, "portion": "100g (1 vagem = 5g = 12 kcal)"},
    "pitanga": {"name": "Pitanga", "category": "lanche", "calories": 41, "protein": 0.7, "carbs": 10.4, "fat": 0.4, "fiber": 0.5, "portion": "100g"},
    "graviola": {"name": "Graviola (fruta-do-conde)", "category": "lanche", "calories": 94, "protein": 1.6, "carbs": 23.5, "fat": 0.5, "fiber": 3.3, "portion": "100g"},
    "siriguela": {"name": "Siriguela", "category": "lanche", "calories": 50, "protein": 0.7, "carbs": 12.5, "fat": 0.4, "fiber": 1.5, "portion": "100g"},
    # ════════════════════════════════════════════════════════════════════════
    # LATICÍNIOS ESPECIAIS / PROT
    # ════════════════════════════════════════════════════════════════════════
    "skyr": {"name": "Skyr (iogurte islandês)", "category": "cafe_manha", "calories": 65, "protein": 11.0, "carbs": 4.0, "fat": 0.2, "fiber": 0.0, "portion": "100g"},
    "queijo_grana": {"name": "Queijo Parmesão Ralado", "category": "almoco", "calories": 420, "protein": 38.5, "carbs": 4.1, "fat": 28.0, "fiber": 0.0, "portion": "100g (1 col. sopa = 7g = 29 kcal)"},
    "leite_amendoas": {"name": "Leite de Amendoas sem Acucar", "category": "cafe_manha", "calories": 15, "protein": 0.6, "carbs": 0.3, "fat": 1.3, "fiber": 0.0, "portion": "100ml"},
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
