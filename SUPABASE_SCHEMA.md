# MELSHAPE — SUPABASE SCHEMA
## Documentação Completa de Tabelas e Views

> Gerado no Sprint 6. Atualizar sempre que uma nova tabela ou view for criada.
> Antes de criar qualquer tabela nova, verificar se já existe aqui (Constituição Cap. IX).

---

## MIGRATIONS OBRIGATÓRIAS (Sprint 4 + Sprint 6)

```sql
-- Sprint 4: Multitenancy
ALTER TABLE profissionais ADD COLUMN IF NOT EXISTS clinic_id text DEFAULT NULL;
ALTER TABLE perfis ADD COLUMN IF NOT EXISTS clinic_id text DEFAULT NULL;
ALTER TABLE perfis ADD COLUMN IF NOT EXISTS meta_cal_custom integer DEFAULT NULL;
ALTER TABLE perfis ADD COLUMN IF NOT EXISTS meta_prot_custom real DEFAULT NULL;

-- Sprint 6: Analytics + Pagamento
CREATE TABLE IF NOT EXISTS eventos_uso (
    id            uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    evento        text NOT NULL,
    propriedades  jsonb DEFAULT '{}',
    perfil_id     text,
    criado_em     timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_eventos_uso_evento ON eventos_uso(evento);
CREATE INDEX IF NOT EXISTS idx_eventos_uso_criado ON eventos_uso(criado_em);

ALTER TABLE profissionais ADD COLUMN IF NOT EXISTS plano_ativo_desde timestamptz;
ALTER TABLE profissionais ADD COLUMN IF NOT EXISTS ultimo_pagamento_id text;
ALTER TABLE profissionais ADD COLUMN IF NOT EXISTS ultimo_pagamento_valor real;

-- Sprint 3: Convites
CREATE TABLE IF NOT EXISTS convites_profissionais (
    id             uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    pro_email      text NOT NULL,
    token          text NOT NULL UNIQUE,
    criado_em      timestamptz DEFAULT now(),
    expira_em      timestamptz NOT NULL,
    usado          boolean DEFAULT false,
    paciente_email text DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_convites_token ON convites_profissionais(token);

-- Sprint 1: Alertas clínicos automáticos
CREATE TABLE IF NOT EXISTS alertas_clinicos (
    id           uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    perfil_id    text NOT NULL,
    titulo       text NOT NULL,
    descricao    text,
    gravidade    integer DEFAULT 1,
    tipo         text DEFAULT 'geral',
    data_alerta  date DEFAULT CURRENT_DATE,
    resolvido    boolean DEFAULT false,
    criado_em    timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_alertas_unico_dia
    ON alertas_clinicos(perfil_id, tipo, data_alerta);
```

---

## TABELAS PRINCIPAIS

### `perfis` — Dados do paciente
```sql
id                uuid PK
email             text UNIQUE NOT NULL
nome_completo     text
data_nascimento   date
sexo              text
altura_cm         integer
peso_atual        real
peso_meta         real
tipo_jornada      text  -- general | fitness | bariatric | glp1
objetivo          text  -- lose | maintain | gain
nivel_atividade   text  -- sedentary | light | moderate | active | very_active
profissional_id   text  -- email do profissional vinculado
clinic_id         text  -- Sprint 4: isolamento por clínica
plano             text  -- free | trial | pro | clinic
onboarding_done   boolean DEFAULT false
meta_cal_custom   integer  -- Sprint 4: sobrescreve cálculo automático
meta_prot_custom  real     -- Sprint 4: sobrescreve cálculo automático
created_at        timestamptz DEFAULT now()
```

### `profissionais` — Dados do profissional
```sql
id                    uuid PK
email                 text UNIQUE NOT NULL
nome_completo         text
especialidade         text
crn                   text
plano                 text  -- pro | clinic | trial
clinic_id             text  -- Sprint 4: agrupa múltiplos profissionais
onboarding_done       boolean DEFAULT false
plano_ativo_desde     timestamptz  -- Sprint 6
ultimo_pagamento_id   text         -- Sprint 6: ID do pagamento MP
ultimo_pagamento_valor real        -- Sprint 6
created_at            timestamptz DEFAULT now()
```

### `checkins` — Check-in diário do paciente
```sql
id              uuid PK
perfil_id       text NOT NULL  -- FK perfis.id
data_checkin    date NOT NULL
humor           integer  -- 1-5
energia         integer  -- 1-5
qualidade_sono  real     -- 1-5
dificuldade     text
vitoria         text
xp_ganho        integer DEFAULT 0
created_at      timestamptz DEFAULT now()
UNIQUE(perfil_id, data_checkin)
```

### `pesagens` — Registros de peso
```sql
id            uuid PK
perfil_id     text NOT NULL
peso          real NOT NULL
data_pesagem  date NOT NULL
observacao    text
created_at    timestamptz DEFAULT now()
```

### `habitos` — Hábitos criados pelo paciente
```sql
id              uuid PK
perfil_id       text NOT NULL
nome            text NOT NULL
icone           text
categoria       text
frequencia      text  -- daily | weekly
ativo           boolean DEFAULT true
created_at      timestamptz DEFAULT now()
```

### `registros_habitos` — Log de hábitos completados
```sql
id          uuid PK
perfil_id   text NOT NULL
habito_id   uuid NOT NULL  -- FK habitos.id
data_log    date NOT NULL
xp_ganho    integer DEFAULT 0
created_at  timestamptz DEFAULT now()
UNIQUE(perfil_id, habito_id, data_log)
```

### `refeicoes` — Refeições registradas
```sql
id              uuid PK
perfil_id       text NOT NULL
tipo_refeicao   text  -- cafe_manha | almoco | jantar | lanche | ceia
data_refeicao   date NOT NULL
calorias_total  real
proteina_total  real
carboidratos_total real
gordura_total   real
created_at      timestamptz DEFAULT now()
```

### `itens_refeicao` — Alimentos de cada refeição
```sql
id           uuid PK
refeicao_id  uuid NOT NULL  -- FK refeicoes.id
alimento_id  text           -- FK foods.id ou alimentos_base.id
nome         text
quantidade_g real
calorias     real
proteina     real
carboidratos real
gordura      real
```

### `metas` — Metas do paciente
```sql
id             uuid PK
perfil_id      text NOT NULL
titulo         text NOT NULL
descricao      text
tipo           text   -- peso | habito | nutricao | conduta
valor_meta     real
valor_atual    real
data_prazo     date
concluida      boolean DEFAULT false
created_at     timestamptz DEFAULT now()
```

### `notificacoes` — Notificações in-app
```sql
id          uuid PK
perfil_id   text NOT NULL
mensagem    text NOT NULL
tipo        text DEFAULT 'engajamento'
lida        boolean DEFAULT false
criado_em   timestamptz DEFAULT now()
```

### `fila_notificacoes` — Fila de entrega de notificações
```sql
id         uuid PK
perfil_id  text NOT NULL
mensagem   text NOT NULL
tipo       text
enviada    boolean DEFAULT false
enviada_em timestamptz
criado_em  timestamptz DEFAULT now()
```

### `condutas_clinicas` — Orientações do profissional
```sql
id             uuid PK
perfil_id      text NOT NULL  -- paciente
pro_email      text NOT NULL
titulo         text NOT NULL
descricao      text
tipo           text  -- orientacao | ajuste_dieta | alerta | elogio | prescricao | encaminhamento | revisao
data_conduta   date DEFAULT CURRENT_DATE
created_at     timestamptz DEFAULT now()
```

### `prescricoes` — Plano ativo do profissional
```sql
id            uuid PK
perfil_id     text NOT NULL
pro_email     text NOT NULL
objetivo      text NOT NULL
data_inicio   date NOT NULL
observacoes   text
ativo         boolean DEFAULT true
created_at    timestamptz DEFAULT now()
```

### `badges` / `badges_usuario` — Gamificação
```sql
-- badges
id      uuid PK
nome    text UNIQUE
titulo  text
descricao text
icone   text
xp      integer DEFAULT 0

-- badges_usuario
id          uuid PK
perfil_id   text NOT NULL
badge_id    uuid NOT NULL  -- FK badges.id
desbloqueado_em timestamptz DEFAULT now()
UNIQUE(perfil_id, badge_id)
```

### `experiencia_usuario` / `historico_xp` — XP e níveis
```sql
-- experiencia_usuario
perfil_id   text PK
xp_total    integer DEFAULT 0
nivel       integer DEFAULT 1
updated_at  timestamptz

-- historico_xp
id          uuid PK
perfil_id   text NOT NULL
xp          integer NOT NULL
motivo      text
criado_em   timestamptz DEFAULT now()
```

### `alertas_clinicos` — Alertas automáticos (Sprint 1)
```sql
id           uuid PK
perfil_id    text NOT NULL
titulo       text NOT NULL
descricao    text
gravidade    integer DEFAULT 1  -- 1=info, 2=atenção, 3=urgente
tipo         text DEFAULT 'geral'
data_alerta  date DEFAULT CURRENT_DATE
resolvido    boolean DEFAULT false
criado_em    timestamptz DEFAULT now()
UNIQUE(perfil_id, tipo, data_alerta)  -- sem duplicatas no mesmo dia
```

### `convites_profissionais` — Convites de pacientes (Sprint 3)
```sql
id             uuid PK
pro_email      text NOT NULL
token          text UNIQUE NOT NULL
criado_em      timestamptz DEFAULT now()
expira_em      timestamptz NOT NULL
usado          boolean DEFAULT false
paciente_email text DEFAULT NULL
```

### `eventos_uso` — Analytics interno (Sprint 6)
```sql
id            uuid PK DEFAULT gen_random_uuid()
evento        text NOT NULL
propriedades  jsonb DEFAULT '{}'
perfil_id     text  -- NULL = anônimo
criado_em     timestamptz DEFAULT now()
```

### Outras tabelas referenciadas
| Tabela | Uso |
|---|---|
| `foods` / `alimentos_base` | Catálogo de alimentos |
| `jornadas` | Jornada do paciente por pilar |
| `etapas_jornada` | Etapas de cada jornada |
| `marcos` | Marcos alcançados na jornada |
| `eventos_vida` | Eventos registrados na jornada |
| `fotos_evolucao` | Fotos de evolução corporal |
| `motivos_jornada` | Motivo da mudança (onboarding) |
| `cirurgias` | Dados bariátricos |
| `fases_bariatricas` | Fases pós-operatórias |
| `sintomas` | Sintomas GLP-1 |
| `treinos` | Registro de treinos |
| `medidas_corporais` | Medidas corporais |
| `registros_agua` | Hidratação diária |
| `suplementos` | Suplementos registrados |
| `sono` | Qualidade do sono |
| `indicadores_clinicos` | Exames e indicadores |
| `consentimentos` | Aceite de termos LGPD |
| `desafios` / `desafios_usuario` | Sistema de desafios |
| `carteira_gamificacao` | Moedas (sem resgate real ainda) |
| `lembretes_recorrentes` | Lembretes personalizados |
| `observacoes_profissionais` | Observações privadas do pro |
| `prescricoes_alimentares` | Plano alimentar estruturado |
| `modelos_refeicao` | Templates de refeição |
| `ciclos` | Ciclos menstruais (futura feature) |
| `historico_notificacoes` | Log histórico de notificações |

---

## VIEWS (`vw_*`)

### Paciente
| View | Uso | Filtro principal |
|---|---|---|
| `vw_dashboard_paciente` | Dados da home do paciente | `perfil_id` |
| `vw_score_transformacao` | Score 5D calculado | `perfil_id` |
| `vw_consumo_diario` | Calorias e macros do dia | `perfil_id, data` |
| `vw_consumo_semanal` | Médias semanais de nutrição | `perfil_id` |
| `vw_evolucao_peso` | Histórico de peso | `perfil_id` |
| `vw_aderencia_nutricional` | % de dias com meta atingida | `perfil_id` |
| `vw_conquistas_usuario` | Badges desbloqueados | `perfil_id` |
| `vw_ranking_gamificacao` | Ranking de XP | — |
| `vw_refeicoes_nutricionais` | Refeições com macros calculados | `perfil_id` |
| `vw_recompensa_pendente` | Conquistas prontas para desbloquear | `perfil_id` |

### Profissional
| View | Uso | Filtro principal |
|---|---|---|
| `vw_fila_atendimento` | Fila de pacientes por prioridade | `profissional_id` |
| `vw_alertas_abertos` | Alertas clínicos não resolvidos | `profissional_id` |
| `vw_alertas_prioritarios` | Alertas de gravidade alta | `profissional_id` |
| `vw_dashboard_profissional` | Métricas do profissional | `profissional_id` |
| `vw_pacientes_inativos` | Pacientes sem check-in há 7+ dias | `profissional_id` |
| `vw_pacientes_para_notificar` | Pacientes com streak em risco | `profissional_id` |
| `vw_sem_checkin_recente` | Sem check-in há 3+ dias | `profissional_id` |
| `vw_prioridade_intervencao` | Score de risco ordenado | `profissional_id` |
| `vw_estagnacao_clinica` | Peso estagnado há 30+ dias | `profissional_id` |

### Clínica / Executive
| View | Uso | Filtro principal |
|---|---|---|
| `vw_resumo_executivo` | KPIs da clínica (total, ativos, aderência) | `clinic_id` |
| `vw_retencao_mensal` | Retenção mês a mês | `clinic_id` |
| `vw_performance_profissionais` | Comparativo entre profissionais | `clinic_id` |
| `vw_campeoes_transformacao` | Top transformações da clínica | `clinic_id` |
| `vw_dashboard_executivo` | Dashboard completo do gestor | `clinic_id` |

---

## POLÍTICAS RLS (Row Level Security)

Recomendado para produção:

```sql
-- Pacientes só veem próprios dados
ALTER TABLE perfis ENABLE ROW LEVEL SECURITY;
CREATE POLICY perfis_own ON perfis
    USING (id = auth.uid()::text OR email = auth.email());

-- Profissional vê só pacientes vinculados
ALTER TABLE checkins ENABLE ROW LEVEL SECURITY;
CREATE POLICY checkins_pro ON checkins
    USING (
        perfil_id = auth.uid()::text
        OR EXISTS (
            SELECT 1 FROM perfis p
            WHERE p.id = checkins.perfil_id
            AND p.profissional_id = auth.email()
        )
    );
```

> Para MVP inicial, RLS pode ficar desativado com controle de acesso no código Python (serviços filtram por `profissional_id` e `clinic_id`). Ativar RLS antes de produção com múltiplos clientes.

---

## WEBHOOK MERCADO PAGO (Sprint 6)

Endpoint necessário no servidor:

```
POST /webhook/mercadopago
Headers: x-signature: <HMAC-SHA256>
Body: { "type": "payment", "data": { "id": "123456789" } }
```

Implementação: `services/payment_service.py` → `PaymentService.process_webhook(body)`

Configuração `.env`:
```
MP_ACCESS_TOKEN=APP_USR-xxxx   # Produção
MP_WEBHOOK_SECRET=xxxx         # Secret para validação HMAC
APP_URL=https://seuapp.com
```

Para Streamlit Cloud: adicionar como Secrets em Settings → Secrets.
