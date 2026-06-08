"""Melshape — Frases motivacionais contextuais."""
import random
from datetime import date

QUOTES: dict = {
    "after_meal": [
        "✨ Cada refeição registrada é um passo em direção à sua meta.",
        "💪 Consistência supera perfeição. Você está no caminho certo.",
        "🌱 Nutrir o corpo é um ato de amor próprio.",
        "🎯 Ótimo registro! Cada dado importa para sua evolução.",
    ],
    "streak_risk": [
        "⚡ Sua sequência está em risco! Registre hoje para mantê-la.",
        "📅 Um dia de cada vez. Você consegue manter a sequência!",
        "🔥 Não deixe a chama apagar. Registre agora!",
    ],
    "glp1": [
        "💉 Com GLP-1, monitorar proteína é ainda mais importante. Continue assim!",
        "🥩 Cada grama de proteína registrado protege sua massa muscular.",
        "💧 Lembre-se de manter a hidratação mesmo sem sentir sede.",
    ],
    "bariatric": [
        "🔪 Pequenas porções, grande transformação. Você está indo muito bem!",
        "💊 Suplementação em dia é parte essencial da sua jornada.",
        "🌟 Cada fase superada é uma vitória. Celebre seu progresso!",
    ],
    "fitness": [
        "🏋️ Treino + nutrição = resultado. Você está combinando os dois!",
        "⚡ A proteína de hoje é o músculo de amanhã.",
        "🎯 Protocolo seguido! Seu corpo agradece.",
    ],
    "general": [
        "🌱 Pequenas mudanças diárias criam grandes transformações.",
        "💪 Você está mais perto do seu objetivo do que ontem.",
        "✨ Cada escolha saudável conta. Continue!",
        "📊 Dados + consistência = resultados reais.",
    ],
    "hydration_ok": [
        "💧 Hidratação em dia! Seu corpo está funcionando melhor agora.",
        "🌊 Água é vida. Parabéns por manter a hidratação!",
    ],
    "sleep_ok": [
        "😴 Sono de qualidade é tão importante quanto a dieta. Ótimo!",
        "🌙 Descanso adequado acelera sua recuperação e metabolismo.",
    ],
}


def get_quote(context: str = "general", health_mode: str = "general") -> str:
    """Retorna frase motivacional baseada no contexto e modo de saúde."""
    # Prioriza contexto específico do modo de saúde
    if health_mode in ("glp1", "bariatric", "fitness") and context == "after_meal":
        pool = QUOTES.get(health_mode, QUOTES["general"])
    else:
        pool = QUOTES.get(context, QUOTES["general"])

    # Seed pelo dia para não variar a cada rerun
    random.seed(date.today().toordinal() + hash(context))
    return random.choice(pool)
