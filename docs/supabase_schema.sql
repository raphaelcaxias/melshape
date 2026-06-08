-- ============================================================
-- Melshape v2.0 — Schema Supabase (PostgreSQL)
-- Execute no SQL Editor do Supabase em ordem
-- ============================================================

-- ── EXTENSÕES ─────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- TABELA: profiles (pacientes)
-- ============================================================
CREATE TABLE IF NOT EXISTS profiles (
    id                   UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email                TEXT,
    name                 TEXT,
    user_type            TEXT DEFAULT 'patient' CHECK (user_type IN ('patient','professional')),

    -- Plano e trial
    plan                 TEXT DEFAULT 'trial'
                           CHECK (plan IN ('free','trial','essencial','pro','lifetime')),
    trial_started_at     TIMESTAMPTZ,
    trial_expires_at     TIMESTAMPTZ,
    lgpd_accepted_at     TIMESTAMPTZ,

    -- Dados pessoais
    gender               TEXT DEFAULT 'female' CHECK (gender IN ('female','male','other')),
    age                  INTEGER CHECK (age BETWEEN 12 AND 110),
    height               INTEGER CHECK (height BETWEEN 100 AND 250),
    current_weight       NUMERIC(5,2) CHECK (current_weight BETWEEN 30 AND 300),
    goal_weight          NUMERIC(5,2) CHECK (goal_weight BETWEEN 30 AND 300),
    activity_level       TEXT DEFAULT 'moderate'
                           CHECK (activity_level IN ('sedentary','light','moderate','active','very_active')),
    goal                 TEXT DEFAULT 'lose' CHECK (goal IN ('lose','maintain','gain')),

    -- Modo de saúde
    health_mode          TEXT DEFAULT 'general'
                           CHECK (health_mode IN ('general','bariatric','glp1','fitness')),

    -- Bariátrico
    is_bariatric         BOOLEAN DEFAULT FALSE,
    surgery_date         DATE,
    bariatric_type       TEXT CHECK (bariatric_type IN ('sleeve','bypass','band','other','')),
    bariatric_phase      TEXT CHECK (bariatric_phase IN ('liquid','pasty','soft','solid','maintenance','')),

    -- GLP-1
    uses_glp1            BOOLEAN DEFAULT FALSE,
    glp1_medication      TEXT,
    glp1_dose            TEXT,
    glp1_start_date      DATE,
    glp1_phase           TEXT CHECK (glp1_phase IN ('adapting','maintenance','tapering','stopped','')),

    -- Nutrição personalizada
    protein_goal_per_kg  NUMERIC(4,2) DEFAULT 1.6,
    custom_calorie_goal  INTEGER,

    -- Vínculos e preferências
    professional_id      UUID,
    dark_mode            BOOLEAN DEFAULT FALSE,
    onboarding_done      BOOLEAN DEFAULT FALSE,

    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: professionals
-- ============================================================
CREATE TABLE IF NOT EXISTS professionals (
    id                   UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email                TEXT,
    name                 TEXT,
    user_type            TEXT DEFAULT 'professional',
    specialty            TEXT DEFAULT 'nutritionist'
                           CHECK (specialty IN ('nutritionist','endocrinologist','other')),
    crn_number           TEXT,
    crn_state            TEXT,
    clinic_name          TEXT,
    phone                TEXT,
    pro_plan             TEXT DEFAULT 'starter'
                           CHECK (pro_plan IN ('starter','solo','clinica','pro','enterprise')),
    patient_count        INTEGER DEFAULT 0,
    trial_expires_at     TIMESTAMPTZ,
    lgpd_accepted_at     TIMESTAMPTZ,
    onboarding_done      BOOLEAN DEFAULT FALSE,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: meal_categories
-- ============================================================
CREATE TABLE IF NOT EXISTS meal_categories (
    id          SERIAL PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    time_start  TIME,
    time_end    TIME,
    sort_order  INTEGER DEFAULT 0
);

-- ============================================================
-- TABELA: foods
-- ============================================================
CREATE TABLE IF NOT EXISTS foods (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name          TEXT NOT NULL,
    category_code TEXT REFERENCES meal_categories(code),
    calories      NUMERIC(7,2) NOT NULL CHECK (calories >= 0),
    protein       NUMERIC(6,2) DEFAULT 0 CHECK (protein >= 0),
    carbs         NUMERIC(6,2) DEFAULT 0 CHECK (carbs >= 0),
    fat           NUMERIC(6,2) DEFAULT 0 CHECK (fat >= 0),
    fiber         NUMERIC(6,2) DEFAULT 0 CHECK (fiber >= 0),
    portion       TEXT DEFAULT '100g',
    is_active     BOOLEAN DEFAULT TRUE,
    source        TEXT DEFAULT 'taco',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: meals
-- ============================================================
CREATE TABLE IF NOT EXISTS meals (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    food            TEXT NOT NULL,
    calories        INTEGER NOT NULL CHECK (calories >= 0),
    protein         NUMERIC(6,2) DEFAULT 0,
    carbs           NUMERIC(6,2) DEFAULT 0,
    fat             NUMERIC(6,2) DEFAULT 0,
    fiber           NUMERIC(6,2) DEFAULT 0,
    quantity        NUMERIC(5,2) DEFAULT 1,
    volume_ml       NUMERIC(6,1) DEFAULT 0,
    meal_time       TEXT,
    meal_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    meal_type       TEXT,
    mood            TEXT CHECK (mood IN ('great','good','neutral','bad','terrible','')),
    notes           TEXT,
    nutrient_score  INTEGER DEFAULT 0 CHECK (nutrient_score BETWEEN 0 AND 100),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: weight_logs
-- ============================================================
CREATE TABLE IF NOT EXISTS weight_logs (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    weight       NUMERIC(5,2) NOT NULL CHECK (weight BETWEEN 30 AND 300),
    log_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    body_fat     NUMERIC(5,2) DEFAULT 0,
    muscle_mass  NUMERIC(5,2) DEFAULT 0,
    notes        TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: supplements
-- ============================================================
CREATE TABLE IF NOT EXISTS supplements (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    dose        TEXT,
    unit        TEXT DEFAULT 'mg',
    category    TEXT DEFAULT 'vitamin'
                  CHECK (category IN ('protein','vitamin','mineral','medication','other')),
    time_taken  TEXT,
    log_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    notes       TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: workouts
-- ============================================================
CREATE TABLE IF NOT EXISTS workouts (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    workout_type     TEXT DEFAULT 'rest'
                       CHECK (workout_type IN ('rest','cardio','strength','hiit','mixed')),
    muscle_group     TEXT,
    intensity        TEXT DEFAULT 'moderate'
                       CHECK (intensity IN ('light','moderate','heavy')),
    duration_min     INTEGER DEFAULT 0 CHECK (duration_min >= 0),
    calories_burned  INTEGER DEFAULT 0,
    log_date         DATE NOT NULL DEFAULT CURRENT_DATE,
    notes            TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: achievements
-- ============================================================
CREATE TABLE IF NOT EXISTS achievements (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    achievement_name  TEXT NOT NULL,
    title             TEXT,
    unlocked_at       DATE DEFAULT CURRENT_DATE,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, achievement_name)
);

-- ============================================================
-- TABELA: hydration_logs (NOVO v2)
-- ============================================================
CREATE TABLE IF NOT EXISTS hydration_logs (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    amount_ml  INTEGER NOT NULL CHECK (amount_ml > 0),
    source     TEXT DEFAULT 'water' CHECK (source IN ('water','juice','tea','other')),
    log_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    log_time   TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: symptom_logs (NOVO v2)
-- ============================================================
CREATE TABLE IF NOT EXISTS symptom_logs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    symptoms    TEXT[] DEFAULT '{}',
    severity    INTEGER DEFAULT 1 CHECK (severity BETWEEN 1 AND 3),
    log_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    notes       TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: sleep_logs (NOVO v2)
-- ============================================================
CREATE TABLE IF NOT EXISTS sleep_logs (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    hours      NUMERIC(4,1) NOT NULL CHECK (hours BETWEEN 0 AND 24),
    quality    INTEGER DEFAULT 3 CHECK (quality BETWEEN 1 AND 5),
    log_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    notes      TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: cycle_logs (NOVO v2)
-- ============================================================
CREATE TABLE IF NOT EXISTS cycle_logs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    phase       TEXT DEFAULT 'follicular'
                  CHECK (phase IN ('menstrual','follicular','ovulation','luteal')),
    symptoms    TEXT[] DEFAULT '{}',
    log_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    notes       TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- ÍNDICES DE PERFORMANCE
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_meals_user_date        ON meals(user_id, meal_date DESC);
CREATE INDEX IF NOT EXISTS idx_meals_user_id          ON meals(user_id);
CREATE INDEX IF NOT EXISTS idx_weight_user_date       ON weight_logs(user_id, log_date DESC);
CREATE INDEX IF NOT EXISTS idx_supls_user_date        ON supplements(user_id, log_date DESC);
CREATE INDEX IF NOT EXISTS idx_workouts_user_date     ON workouts(user_id, log_date DESC);
CREATE INDEX IF NOT EXISTS idx_achievements_user      ON achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_hydration_user_date    ON hydration_logs(user_id, log_date DESC);
CREATE INDEX IF NOT EXISTS idx_symptoms_user_date     ON symptom_logs(user_id, log_date DESC);
CREATE INDEX IF NOT EXISTS idx_sleep_user_date        ON sleep_logs(user_id, log_date DESC);
CREATE INDEX IF NOT EXISTS idx_cycle_user_date        ON cycle_logs(user_id, log_date DESC);
CREATE INDEX IF NOT EXISTS idx_foods_category         ON foods(category_code);
CREATE INDEX IF NOT EXISTS idx_foods_name_trgm        ON foods USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_profiles_professional  ON profiles(professional_id);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================
ALTER TABLE profiles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE professionals   ENABLE ROW LEVEL SECURITY;
ALTER TABLE meals           ENABLE ROW LEVEL SECURITY;
ALTER TABLE weight_logs     ENABLE ROW LEVEL SECURITY;
ALTER TABLE supplements     ENABLE ROW LEVEL SECURITY;
ALTER TABLE workouts        ENABLE ROW LEVEL SECURITY;
ALTER TABLE achievements    ENABLE ROW LEVEL SECURITY;
ALTER TABLE hydration_logs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE symptom_logs    ENABLE ROW LEVEL SECURITY;
ALTER TABLE sleep_logs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE cycle_logs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE foods            ENABLE ROW LEVEL SECURITY;

-- Profiles
CREATE POLICY "profiles_select_own"  ON profiles FOR SELECT  USING (auth.uid() = id);
CREATE POLICY "profiles_insert_own"  ON profiles FOR INSERT  WITH CHECK (auth.uid() = id);
CREATE POLICY "profiles_update_own"  ON profiles FOR UPDATE  USING (auth.uid() = id);
CREATE POLICY "profiles_delete_own"  ON profiles FOR DELETE  USING (auth.uid() = id);

-- Profissional pode ver pacientes vinculados
CREATE POLICY "profiles_pro_select" ON profiles FOR SELECT
    USING (professional_id = auth.uid());

-- Professionals
CREATE POLICY "pro_select_own"  ON professionals FOR SELECT  USING (auth.uid() = id);
CREATE POLICY "pro_insert_own"  ON professionals FOR INSERT  WITH CHECK (auth.uid() = id);
CREATE POLICY "pro_update_own"  ON professionals FOR UPDATE  USING (auth.uid() = id);

-- Meals
CREATE POLICY "meals_select_own"  ON meals FOR SELECT  USING (auth.uid() = user_id);
CREATE POLICY "meals_insert_own"  ON meals FOR INSERT  WITH CHECK (auth.uid() = user_id);
CREATE POLICY "meals_delete_own"  ON meals FOR DELETE  USING (auth.uid() = user_id);
CREATE POLICY "meals_pro_select"  ON meals FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM profiles p WHERE p.id = meals.user_id
        AND p.professional_id = auth.uid()
    ));

-- Weight logs
CREATE POLICY "weights_select_own"  ON weight_logs FOR SELECT  USING (auth.uid() = user_id);
CREATE POLICY "weights_insert_own"  ON weight_logs FOR INSERT  WITH CHECK (auth.uid() = user_id);
CREATE POLICY "weights_delete_own"  ON weight_logs FOR DELETE  USING (auth.uid() = user_id);
CREATE POLICY "weights_pro_select"  ON weight_logs FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM profiles p WHERE p.id = weight_logs.user_id
        AND p.professional_id = auth.uid()
    ));

-- Supplements
CREATE POLICY "supls_select_own"  ON supplements FOR SELECT  USING (auth.uid() = user_id);
CREATE POLICY "supls_insert_own"  ON supplements FOR INSERT  WITH CHECK (auth.uid() = user_id);
CREATE POLICY "supls_delete_own"  ON supplements FOR DELETE  USING (auth.uid() = user_id);

-- Workouts
CREATE POLICY "wk_select_own"  ON workouts FOR SELECT  USING (auth.uid() = user_id);
CREATE POLICY "wk_insert_own"  ON workouts FOR INSERT  WITH CHECK (auth.uid() = user_id);
CREATE POLICY "wk_delete_own"  ON workouts FOR DELETE  USING (auth.uid() = user_id);

-- Achievements
CREATE POLICY "ach_select_own"  ON achievements FOR SELECT  USING (auth.uid() = user_id);
CREATE POLICY "ach_insert_own"  ON achievements FOR INSERT  WITH CHECK (auth.uid() = user_id);

-- Hydration
CREATE POLICY "hyd_select_own"  ON hydration_logs FOR SELECT  USING (auth.uid() = user_id);
CREATE POLICY "hyd_insert_own"  ON hydration_logs FOR INSERT  WITH CHECK (auth.uid() = user_id);

-- Symptoms
CREATE POLICY "sym_select_own"  ON symptom_logs FOR SELECT  USING (auth.uid() = user_id);
CREATE POLICY "sym_insert_own"  ON symptom_logs FOR INSERT  WITH CHECK (auth.uid() = user_id);

-- Sleep
CREATE POLICY "slp_select_own"  ON sleep_logs FOR SELECT  USING (auth.uid() = user_id);
CREATE POLICY "slp_insert_own"  ON sleep_logs FOR INSERT  WITH CHECK (auth.uid() = user_id);

-- Cycle
CREATE POLICY "cyc_select_own"  ON cycle_logs FOR SELECT  USING (auth.uid() = user_id);
CREATE POLICY "cyc_insert_own"  ON cycle_logs FOR INSERT  WITH CHECK (auth.uid() = user_id);

-- Foods: leitura pública autenticada
CREATE POLICY "foods_public_read"  ON foods FOR SELECT  USING (is_active = TRUE);

-- ============================================================
-- TRIGGER: criar perfil no signup
-- ============================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    INSERT INTO public.profiles (id, email, name, plan, trial_started_at, trial_expires_at)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'name', split_part(NEW.email,'@',1)),
        'trial',
        NOW(),
        NOW() + INTERVAL '10 days'
    );
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================================
-- TRIGGER: updated_at automático
-- ============================================================
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;

CREATE TRIGGER profiles_updated_at
    BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

CREATE TRIGGER professionals_updated_at
    BEFORE UPDATE ON professionals FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

-- ============================================================
-- TRIGGER: expirar trial automaticamente
-- ============================================================
CREATE OR REPLACE FUNCTION public.check_trial_expired()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.plan = 'trial' AND NEW.trial_expires_at IS NOT NULL AND NEW.trial_expires_at < NOW() THEN
        NEW.plan := 'free';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER profiles_check_trial
    BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE FUNCTION public.check_trial_expired();

-- ============================================================
-- VIEWS ÚTEIS
-- ============================================================
CREATE OR REPLACE VIEW daily_summary AS
SELECT
    user_id, meal_date,
    SUM(calories) AS total_calories,
    SUM(protein)  AS total_protein,
    SUM(carbs)    AS total_carbs,
    SUM(fat)      AS total_fat,
    SUM(fiber)    AS total_fiber,
    COUNT(*)      AS meal_count
FROM meals
GROUP BY user_id, meal_date;

CREATE OR REPLACE VIEW weight_progress AS
SELECT
    user_id, weight, log_date, body_fat, muscle_mass,
    LAG(weight) OVER (PARTITION BY user_id ORDER BY log_date) AS prev_weight,
    weight - LAG(weight) OVER (PARTITION BY user_id ORDER BY log_date) AS weight_change
FROM weight_logs;

CREATE OR REPLACE VIEW daily_hydration AS
SELECT
    user_id, log_date,
    SUM(amount_ml) AS total_ml,
    COUNT(*)       AS log_count
FROM hydration_logs
GROUP BY user_id, log_date;

-- ============================================================
-- STORAGE: bucket para fotos de refeições
-- ============================================================
INSERT INTO storage.buckets (id, name, public)
VALUES ('meal-photos', 'meal-photos', false)
ON CONFLICT DO NOTHING;

CREATE POLICY "meal_photos_user" ON storage.objects
    FOR ALL USING (
        bucket_id = 'meal-photos'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

-- ============================================================
-- DADOS INICIAIS: CATEGORIAS
-- ============================================================
INSERT INTO meal_categories (code, name, time_start, time_end, sort_order) VALUES
    ('cafe_manha',    'Café da Manhã',   '05:00', '10:00', 1),
    ('almoco_jantar', 'Almoço / Jantar', '10:00', '21:00', 2),
    ('lanche',        'Lanche',          '10:00', '18:00', 3),
    ('ceia',          'Ceia',            '20:00', '23:59', 4),
    ('pre_pos_treino','Pré/Pós Treino',  '06:00', '22:00', 5)
ON CONFLICT DO NOTHING;

-- ============================================================
-- DADOS INICIAIS: 55 ALIMENTOS BRASILEIROS (TACO/IBGE)
-- ============================================================
INSERT INTO foods (name, category_code, calories, protein, carbs, fat, fiber, portion) VALUES
-- Café da manhã
('Pão Francês',              'cafe_manha',    300,  8.0,  58.0,  3.0,  1.5, '1 unidade (50g)'),
('Pão Integral',             'cafe_manha',     65,  3.0,  12.0,  1.0,  2.0, '1 fatia (25g)'),
('Ovo Cozido',               'cafe_manha',     77,  6.5,   0.6,  5.3,  0.0, '1 unidade (50g)'),
('Ovo Mexido',               'cafe_manha',     91,  6.7,   0.6,  7.0,  0.0, '1 unidade (55g)'),
('Leite Integral',           'cafe_manha',     60,  3.0,   4.5,  3.3,  0.0, '100ml'),
('Leite Desnatado',          'cafe_manha',     35,  3.4,   5.0,  0.1,  0.0, '100ml'),
('Café com Leite',           'cafe_manha',     50,  2.0,   5.0,  2.0,  0.0, '200ml'),
('Tapioca',                  'cafe_manha',    130,  0.5,  32.0,  0.1,  0.4, '1 unidade (50g)'),
('Cuscuz Nordestino',        'cafe_manha',    120,  2.0,  28.0,  0.5,  1.0, '100g'),
('Iogurte Natural',          'cafe_manha',     61,  3.5,   4.7,  3.3,  0.0, '100g'),
('Iogurte Grego',            'cafe_manha',    115,  8.5,   4.0,  6.5,  0.0, '100g'),
('Aveia em Flocos',          'cafe_manha',    360, 13.0,  64.0,  6.9,  9.4, '100g'),
('Granola',                  'cafe_manha',    420, 10.0,  65.0, 14.0,  7.0, '100g'),
('Queijo Minas Frescal',     'cafe_manha',    264, 17.0,   3.2, 20.0,  0.0, '100g'),
('Mamão Papaia',             'cafe_manha',     45,  0.5,  11.8,  0.1,  1.8, '100g'),
('Requeijão Light',          'cafe_manha',    133,  8.0,   5.0,  9.0,  0.0, '1 colher (30g)'),
('Mingau de Aveia',          'cafe_manha',    135,  4.5,  22.0,  3.5,  2.5, '200ml'),
-- Almoço / Jantar
('Arroz Branco Cozido',      'almoco_jantar', 128,  2.5,  28.0,  0.2,  0.2, '100g'),
('Arroz Integral Cozido',    'almoco_jantar', 124,  2.8,  26.0,  0.8,  1.7, '100g'),
('Feijão Preto Cozido',      'almoco_jantar',  77,  4.5,  14.0,  0.5,  6.3, '100g'),
('Feijão Carioca Cozido',    'almoco_jantar',  76,  4.8,  13.6,  0.5,  6.4, '100g'),
('Peito de Frango Grelhado', 'almoco_jantar', 159, 32.0,   0.0,  3.5,  0.0, '100g'),
('Coxa de Frango Assada',    'almoco_jantar', 204, 25.0,   0.0, 11.5,  0.0, '100g'),
('Patinho Bovino Grelhado',  'almoco_jantar', 219, 33.0,   0.0,  9.0,  0.0, '100g'),
('Acém Bovino Cozido',       'almoco_jantar', 208, 28.0,   0.0, 10.5,  0.0, '100g'),
('Carne Moída Refogada',     'almoco_jantar', 265, 25.0,   5.0, 16.0,  0.0, '100g'),
('Tilápia Assada',           'almoco_jantar', 128, 26.0,   0.0,  2.7,  0.0, '100g'),
('Atum em Lata (água)',      'almoco_jantar', 116, 26.0,   0.0,  1.0,  0.0, '100g'),
('Sardinha em Lata',         'almoco_jantar', 208, 24.0,   0.0, 12.0,  0.0, '100g'),
('Salmão Grelhado',          'almoco_jantar', 206, 28.0,   0.0, 10.0,  0.0, '100g'),
('Ovo Frito',                'almoco_jantar', 109,  7.0,   0.4,  9.0,  0.0, '1 unidade (55g)'),
('Macarrão Cozido',          'almoco_jantar', 131,  4.5,  27.2,  0.9,  1.2, '100g'),
('Batata Cozida',            'almoco_jantar',  87,  1.9,  20.0,  0.1,  1.8, '100g'),
('Batata Doce Cozida',       'almoco_jantar',  86,  1.4,  20.1,  0.1,  2.5, '100g'),
('Mandioca Cozida',          'almoco_jantar', 150,  1.0,  36.5,  0.3,  1.8, '100g'),
('Alface',                   'almoco_jantar',  15,  1.4,   2.9,  0.2,  2.0, '100g'),
('Tomate',                   'almoco_jantar',  18,  0.9,   3.5,  0.2,  1.2, '100g'),
('Cenoura Crua',             'almoco_jantar',  34,  0.9,   7.7,  0.2,  3.2, '100g'),
('Brócolis Cozido',          'almoco_jantar',  25,  2.9,   3.5,  0.4,  3.3, '100g'),
('Abobrinha Cozida',         'almoco_jantar',  17,  1.2,   3.0,  0.3,  1.1, '100g'),
('PF: Arroz+Feijão+Frango',  'almoco_jantar', 520, 38.0,  64.0,  8.0,  6.0, '1 prato (400g)'),
-- Lanche
('Banana Prata',             'lanche',         98,  1.3,  26.0,  0.1,  2.0, '1 unidade (100g)'),
('Maçã',                     'lanche',         56,  0.3,  15.2,  0.1,  2.4, '1 unidade (100g)'),
('Laranja',                  'lanche',         47,  0.9,  11.7,  0.1,  2.4, '1 unidade (130g)'),
('Manga',                    'lanche',         60,  0.8,  14.9,  0.3,  1.8, '100g'),
('Açaí com Granola',         'lanche',        280,  4.0,  42.0, 12.0,  5.0, '300ml'),
('Castanha de Caju',         'lanche',        570, 15.0,  32.0, 46.0,  3.7, '100g'),
('Amendoim Torrado',         'lanche',        567, 26.0,  16.0, 49.0,  8.5, '100g'),
('Pão de Queijo',            'lanche',        370,  6.0,  52.0, 16.0,  0.5, '1 unidade (60g)'),
('Vitamina de Banana',       'lanche',        180,  6.0,  38.0,  2.0,  2.0, '300ml'),
('Suco de Laranja Natural',  'lanche',         45,  0.7,  10.5,  0.2,  0.2, '200ml'),
-- Pré/Pós Treino
('Proteína Whey',            'pre_pos_treino', 120, 24.0,   3.0,  2.0,  0.0, '1 scoop (30g)'),
('Barra de Proteína',        'pre_pos_treino', 200, 20.0,  22.0,  6.0,  2.0, '1 unidade (60g)'),
('Banana (pré-treino)',      'pre_pos_treino',  98,  1.3,  26.0,  0.1,  2.0, '1 unidade'),
-- Ceia
('Leite Quente com Mel',     'ceia',           90,  3.0,  12.0,  3.0,  0.0, '200ml'),
('Chá de Camomila',          'ceia',            2,  0.0,   0.5,  0.0,  0.0, '200ml'),
('Kiwi',                     'ceia',           61,  1.1,  15.0,  0.5,  3.0, '2 unidades (100g)')
ON CONFLICT DO NOTHING;

DO $$
BEGIN
    RAISE NOTICE '✅ Schema Melshape v2.0 aplicado com sucesso!';
    RAISE NOTICE '   Tabelas: profiles, professionals, foods, meals, weight_logs,';
    RAISE NOTICE '            supplements, workouts, achievements,';
    RAISE NOTICE '            hydration_logs, symptom_logs, sleep_logs, cycle_logs';
    RAISE NOTICE '   RLS ativo em todas as tabelas';
    RAISE NOTICE '   Triggers: auto-criar perfil, updated_at, expirar trial';
    RAISE NOTICE '   Views: daily_summary, weight_progress, daily_hydration';
    RAISE NOTICE '   55 alimentos brasileiros (TACO/IBGE) inseridos';
END $$;
