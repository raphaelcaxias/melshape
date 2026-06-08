"""
Melshape — Banco de alimentos com cache de 1 hora.
Busca normalizada sem acento + ordenação por frequência.
"""
import logging
import unicodedata
from typing import List, Dict, Any, Optional
import streamlit as st

logger = logging.getLogger("Melshape.Food")


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


FALLBACK_FOODS: Dict[str, Dict[str, Any]] = {
    # CAFÉ DA MANHÃ
    "pao_frances":     {"name":"Pão Francês",           "category":"cafe_manha",    "calories":300, "protein":8.0,  "carbs":58.0, "fat":3.0,  "fiber":1.5,"portion":"1 unidade (50g)"},
    "pao_integral":    {"name":"Pão Integral",           "category":"cafe_manha",    "calories":65,  "protein":3.0,  "carbs":12.0, "fat":1.0,  "fiber":2.0,"portion":"1 fatia (25g)"},
    "ovo_cozido":      {"name":"Ovo Cozido",             "category":"cafe_manha",    "calories":77,  "protein":6.5,  "carbs":0.6,  "fat":5.3,  "fiber":0.0,"portion":"1 unidade (50g)"},
    "ovo_mexido":      {"name":"Ovo Mexido",             "category":"cafe_manha",    "calories":91,  "protein":6.7,  "carbs":0.6,  "fat":7.0,  "fiber":0.0,"portion":"1 unidade (55g)"},
    "leite_integral":  {"name":"Leite Integral",         "category":"cafe_manha",    "calories":60,  "protein":3.0,  "carbs":4.5,  "fat":3.3,  "fiber":0.0,"portion":"100ml"},
    "leite_desnatado": {"name":"Leite Desnatado",        "category":"cafe_manha",    "calories":35,  "protein":3.4,  "carbs":5.0,  "fat":0.1,  "fiber":0.0,"portion":"100ml"},
    "cafe_leite":      {"name":"Café com Leite",         "category":"cafe_manha",    "calories":50,  "protein":2.0,  "carbs":5.0,  "fat":2.0,  "fiber":0.0,"portion":"200ml"},
    "tapioca":         {"name":"Tapioca",                "category":"cafe_manha",    "calories":130, "protein":0.5,  "carbs":32.0, "fat":0.1,  "fiber":0.4,"portion":"1 unidade (50g)"},
    "cuscuz":          {"name":"Cuscuz Nordestino",      "category":"cafe_manha",    "calories":120, "protein":2.0,  "carbs":28.0, "fat":0.5,  "fiber":1.0,"portion":"100g"},
    "iogurte_natural": {"name":"Iogurte Natural",        "category":"cafe_manha",    "calories":61,  "protein":3.5,  "carbs":4.7,  "fat":3.3,  "fiber":0.0,"portion":"100g"},
    "iogurte_grego":   {"name":"Iogurte Grego",         "category":"cafe_manha",    "calories":115, "protein":8.5,  "carbs":4.0,  "fat":6.5,  "fiber":0.0,"portion":"100g"},
    "aveia":           {"name":"Aveia em Flocos",        "category":"cafe_manha",    "calories":360, "protein":13.0, "carbs":64.0, "fat":6.9,  "fiber":9.4,"portion":"100g"},
    "granola":         {"name":"Granola",                "category":"cafe_manha",    "calories":420, "protein":10.0, "carbs":65.0, "fat":14.0, "fiber":7.0,"portion":"100g"},
    "queijo_minas":    {"name":"Queijo Minas Frescal",   "category":"cafe_manha",    "calories":264, "protein":17.0, "carbs":3.2,  "fat":20.0, "fiber":0.0,"portion":"100g"},
    "mamao":           {"name":"Mamão Papaia",           "category":"cafe_manha",    "calories":45,  "protein":0.5,  "carbs":11.8, "fat":0.1,  "fiber":1.8,"portion":"100g"},
    "requeijao_light": {"name":"Requeijão Light",        "category":"cafe_manha",    "calories":133, "protein":8.0,  "carbs":5.0,  "fat":9.0,  "fiber":0.0,"portion":"1 colher (30g)"},
    "mingau_aveia":    {"name":"Mingau de Aveia",        "category":"cafe_manha",    "calories":135, "protein":4.5,  "carbs":22.0, "fat":3.5,  "fiber":2.5,"portion":"200ml"},
    # ALMOÇO / JANTAR
    "arroz_branco":    {"name":"Arroz Branco Cozido",    "category":"almoco_jantar", "calories":128, "protein":2.5,  "carbs":28.0, "fat":0.2,  "fiber":0.2,"portion":"100g"},
    "arroz_integral":  {"name":"Arroz Integral Cozido",  "category":"almoco_jantar", "calories":124, "protein":2.8,  "carbs":26.0, "fat":0.8,  "fiber":1.7,"portion":"100g"},
    "feijao_preto":    {"name":"Feijão Preto Cozido",    "category":"almoco_jantar", "calories":77,  "protein":4.5,  "carbs":14.0, "fat":0.5,  "fiber":6.3,"portion":"100g"},
    "feijao_carioca":  {"name":"Feijão Carioca Cozido",  "category":"almoco_jantar", "calories":76,  "protein":4.8,  "carbs":13.6, "fat":0.5,  "fiber":6.4,"portion":"100g"},
    "frango_peito":    {"name":"Peito de Frango Grelhado","category":"almoco_jantar","calories":159, "protein":32.0, "carbs":0.0,  "fat":3.5,  "fiber":0.0,"portion":"100g"},
    "frango_coxa":     {"name":"Coxa de Frango Assada",  "category":"almoco_jantar", "calories":204, "protein":25.0, "carbs":0.0,  "fat":11.5, "fiber":0.0,"portion":"100g"},
    "patinho":         {"name":"Patinho Bovino Grelhado","category":"almoco_jantar", "calories":219, "protein":33.0, "carbs":0.0,  "fat":9.0,  "fiber":0.0,"portion":"100g"},
    "acem":            {"name":"Acém Bovino Cozido",     "category":"almoco_jantar", "calories":208, "protein":28.0, "carbs":0.0,  "fat":10.5, "fiber":0.0,"portion":"100g"},
    "carne_moida":     {"name":"Carne Moída Refogada",   "category":"almoco_jantar", "calories":265, "protein":25.0, "carbs":5.0,  "fat":16.0, "fiber":0.0,"portion":"100g"},
    "tilapia":         {"name":"Tilápia Assada",         "category":"almoco_jantar", "calories":128, "protein":26.0, "carbs":0.0,  "fat":2.7,  "fiber":0.0,"portion":"100g"},
    "atum_lata":       {"name":"Atum em Lata (água)",    "category":"almoco_jantar", "calories":116, "protein":26.0, "carbs":0.0,  "fat":1.0,  "fiber":0.0,"portion":"100g"},
    "sardinha":        {"name":"Sardinha em Lata",       "category":"almoco_jantar", "calories":208, "protein":24.0, "carbs":0.0,  "fat":12.0, "fiber":0.0,"portion":"100g"},
    "salmao":          {"name":"Salmão Grelhado",        "category":"almoco_jantar", "calories":206, "protein":28.0, "carbs":0.0,  "fat":10.0, "fiber":0.0,"portion":"100g"},
    "ovo_frito":       {"name":"Ovo Frito",              "category":"almoco_jantar", "calories":109, "protein":7.0,  "carbs":0.4,  "fat":9.0,  "fiber":0.0,"portion":"1 unidade (55g)"},
    "macarrao":        {"name":"Macarrão Cozido",        "category":"almoco_jantar", "calories":131, "protein":4.5,  "carbs":27.2, "fat":0.9,  "fiber":1.2,"portion":"100g"},
    "batata_cozida":   {"name":"Batata Cozida",          "category":"almoco_jantar", "calories":87,  "protein":1.9,  "carbs":20.0, "fat":0.1,  "fiber":1.8,"portion":"100g"},
    "batata_doce":     {"name":"Batata Doce Cozida",     "category":"almoco_jantar", "calories":86,  "protein":1.4,  "carbs":20.1, "fat":0.1,  "fiber":2.5,"portion":"100g"},
    "mandioca":        {"name":"Mandioca Cozida",        "category":"almoco_jantar", "calories":150, "protein":1.0,  "carbs":36.5, "fat":0.3,  "fiber":1.8,"portion":"100g"},
    "alface":          {"name":"Alface",                 "category":"almoco_jantar", "calories":15,  "protein":1.4,  "carbs":2.9,  "fat":0.2,  "fiber":2.0,"portion":"100g"},
    "tomate":          {"name":"Tomate",                 "category":"almoco_jantar", "calories":18,  "protein":0.9,  "carbs":3.5,  "fat":0.2,  "fiber":1.2,"portion":"100g"},
    "cenoura":         {"name":"Cenoura Crua",           "category":"almoco_jantar", "calories":34,  "protein":0.9,  "carbs":7.7,  "fat":0.2,  "fiber":3.2,"portion":"100g"},
    "brocolis":        {"name":"Brócolis Cozido",        "category":"almoco_jantar", "calories":25,  "protein":2.9,  "carbs":3.5,  "fat":0.4,  "fiber":3.3,"portion":"100g"},
    "abobrinha":       {"name":"Abobrinha Cozida",       "category":"almoco_jantar", "calories":17,  "protein":1.2,  "carbs":3.0,  "fat":0.3,  "fiber":1.1,"portion":"100g"},
    "pf_completo":     {"name":"PF: Arroz+Feijão+Frango","category":"almoco_jantar","calories":520, "protein":38.0, "carbs":64.0, "fat":8.0,  "fiber":6.0,"portion":"1 prato (400g)"},
    # LANCHE
    "banana_prata":    {"name":"Banana Prata",           "category":"lanche",        "calories":98,  "protein":1.3,  "carbs":26.0, "fat":0.1,  "fiber":2.0,"portion":"1 unidade (100g)"},
    "maca":            {"name":"Maçã",                   "category":"lanche",        "calories":56,  "protein":0.3,  "carbs":15.2, "fat":0.1,  "fiber":2.4,"portion":"1 unidade (100g)"},
    "laranja":         {"name":"Laranja",                "category":"lanche",        "calories":47,  "protein":0.9,  "carbs":11.7, "fat":0.1,  "fiber":2.4,"portion":"1 unidade (130g)"},
    "manga":           {"name":"Manga",                  "category":"lanche",        "calories":60,  "protein":0.8,  "carbs":14.9, "fat":0.3,  "fiber":1.8,"portion":"100g"},
    "acai":            {"name":"Açaí com Granola",       "category":"lanche",        "calories":280, "protein":4.0,  "carbs":42.0, "fat":12.0, "fiber":5.0,"portion":"300ml"},
    "castanha_caju":   {"name":"Castanha de Caju",       "category":"lanche",        "calories":570, "protein":15.0, "carbs":32.0, "fat":46.0, "fiber":3.7,"portion":"100g"},
    "amendoim":        {"name":"Amendoim Torrado",       "category":"lanche",        "calories":567, "protein":26.0, "carbs":16.0, "fat":49.0, "fiber":8.5,"portion":"100g"},
    "pao_queijo":      {"name":"Pão de Queijo",          "category":"lanche",        "calories":370, "protein":6.0,  "carbs":52.0, "fat":16.0, "fiber":0.5,"portion":"1 unidade (60g)"},
    "vitamina_banana": {"name":"Vitamina de Banana",     "category":"lanche",        "calories":180, "protein":6.0,  "carbs":38.0, "fat":2.0,  "fiber":2.0,"portion":"300ml"},
    "suco_laranja":    {"name":"Suco de Laranja Natural","category":"lanche",        "calories":45,  "protein":0.7,  "carbs":10.5, "fat":0.2,  "fiber":0.2,"portion":"200ml"},
    # PRÉ/PÓS TREINO
    "whey":            {"name":"Proteína Whey",          "category":"pre_pos_treino","calories":120, "protein":24.0, "carbs":3.0,  "fat":2.0,  "fiber":0.0,"portion":"1 scoop (30g)"},
    "barra_proteina":  {"name":"Barra de Proteína",      "category":"pre_pos_treino","calories":200, "protein":20.0, "carbs":22.0, "fat":6.0,  "fiber":2.0,"portion":"1 unidade (60g)"},
    "banana_treino":   {"name":"Banana (pré-treino)",    "category":"pre_pos_treino","calories":98,  "protein":1.3,  "carbs":26.0, "fat":0.1,  "fiber":2.0,"portion":"1 unidade"},
    # CEIA
    "leite_quente":    {"name":"Leite Quente com Mel",   "category":"ceia",          "calories":90,  "protein":3.0,  "carbs":12.0, "fat":3.0,  "fiber":0.0,"portion":"200ml"},
    "cha_camomila":    {"name":"Chá de Camomila",        "category":"ceia",          "calories":2,   "protein":0.0,  "carbs":0.5,  "fat":0.0,  "fiber":0.0,"portion":"200ml"},
    "kiwi":            {"name":"Kiwi",                   "category":"ceia",          "calories":61,  "protein":1.1,  "carbs":15.0, "fat":0.5,  "fiber":3.0,"portion":"2 unidades (100g)"},
}


# ── Cache do banco de alimentos por categoria (1 hora) ────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _get_fallback_by_category(category_code: str) -> List[Dict[str, Any]]:
    return [v for v in FALLBACK_FOODS.values() if v.get("category") == category_code]


@st.cache_data(ttl=3600, show_spinner=False)
def _get_all_fallback() -> List[Dict[str, Any]]:
    return list(FALLBACK_FOODS.values())


class FoodService:
    """Busca de alimentos: Supabase → fallback local com normalização."""

    def __init__(self, client=None):
        self.client       = client
        self.use_supabase = client is not None

    def get_foods_by_category(self, category_code: str) -> List[Dict[str, Any]]:
        if self.use_supabase:
            try:
                r = (self.client.table("foods").select("*")
                     .eq("category_code", category_code)
                     .eq("is_active", True).order("name").execute())
                if r.data:
                    return r.data
            except Exception as e:
                logger.warning(f"Supabase foods: {e}")
        return _get_fallback_by_category(category_code)

    def search_foods(self, term: str,
                     category_code: Optional[str] = None,
                     frequent_foods: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        if self.use_supabase and term:
            try:
                q = (self.client.table("foods").select("*")
                     .ilike("name", f"%{term}%").eq("is_active", True))
                if category_code:
                    q = q.eq("category_code", category_code)
                r = q.limit(30).execute()
                if r.data:
                    return r.data
            except Exception as e:
                logger.warning(f"Supabase search: {e}")

        norm_term = _normalize(term) if term else ""
        results   = [
            v for v in FALLBACK_FOODS.values()
            if (not category_code or v.get("category") == category_code)
            and (not norm_term or norm_term in _normalize(v["name"]))
        ]
        if frequent_foods:
            freq_set = set(frequent_foods)
            results.sort(key=lambda x: (0 if x["name"] in freq_set else 1, x["name"]))
        return results

    def get_all_foods(self) -> List[Dict[str, Any]]:
        if self.use_supabase:
            try:
                r = (self.client.table("foods").select("*")
                     .eq("is_active", True).order("name").execute())
                if r.data:
                    return r.data
            except Exception:
                pass
        return _get_all_fallback()
