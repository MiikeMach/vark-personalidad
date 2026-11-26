# 3. Modelo físico de la base de datos

El modelo físico se deriva directamente de las migraciones de Django y del DER exportado desde pgAdmin. Todas las tablas residen en el esquema `public` de PostgreSQL 18.

## 3.1. DER (Mermaid)

erDiagram
    students_grupo ||--o{ students_estudiante : contiene
    questionnaires_cuestionario ||--o{ questionnaires_pregunta : tiene
    questionnaires_pregunta ||--o{ questionnaires_opcion : ofrece
    students_estudiante ||--o{ assessments_evaluacion : realiza
    questionnaires_cuestionario ||--o{ assessments_evaluacion : aplica
    assessments_evaluacion ||--o{ assessments_respuesta : registra
    questionnaires_pregunta ||--o{ assessments_respuesta : responde
    assessments_respuesta ||--o{ assessments_seleccionrespuesta : selecciona
    questionnaires_opcion ||--o{ assessments_seleccionrespuesta : elegida
    assessments_evaluacion ||--|| results_resultado : genera
    results_resultado ||--o{ results_puntajedimension : desglosa

    students_grupo {
        bigint id PK
        varchar clave UK
        varchar nombre
        boolean activo
        timestamptz creado_en
    }
    students_estudiante {
        bigint id PK
        varchar matricula UK
        varchar nombres
        varchar apellidos
        varchar correo
        boolean activo
        timestamptz creado_en
        bigint grupo_id FK
    }
    questionnaires_cuestionario {
        bigint id PK
        varchar titulo
        text descripcion
        text instrucciones
        varchar tipo
        boolean activo
        timestamptz creado_en
    }
    questionnaires_pregunta {
        bigint id PK
        text texto
        int orden
        bigint cuestionario_id FK
    }
    questionnaires_opcion {
        bigint id PK
        text texto
        varchar dimension
        int orden
        bigint pregunta_id FK
    }
    assessments_evaluacion {
        bigint id PK
        varchar estado
        timestamptz iniciada_en
        timestamptz finalizada_en
        bigint cuestionario_id FK
        bigint estudiante_id FK
    }
    assessments_respuesta {
        bigint id PK
        bigint evaluacion_id FK
        bigint pregunta_id FK
    }
    assessments_seleccionrespuesta {
        bigint id PK
        smallint puntos
        bigint opcion_id FK
        bigint respuesta_id FK
    }
    results_resultado {
        bigint id PK
        int preguntas_contestadas
        int preguntas_omitidas
        text interpretacion
        timestamptz calculado_en
        bigint evaluacion_id FK,UK
    }
    results_puntajedimension {
        bigint id PK
        varchar dimension
        int puntaje
        bigint resultado_id FK
    }

## 3.2. Diccionario de tablas
### 3.2.1. students_grupo

|Columna | Tipo	| Restricciones |
|---|---|---|
|id	| bigint | PK, IDENTITY |
|clave | varchar(20) | UNIQUE, NOT NULL |
|nombre	| varchar(100) | NOT NULL |
|activo | boolean | NOT NULL, default true |
|creado_en | timestamptz | NOT NULL, auto |

### 3.2.2. students_estudiante

|Columna | Tipo	| Restricciones |
|---|---|---|
|id	| bigint | PK |
|matricula | varchar(30) | UNIQUE, NOT NULL |
|nombres | varchar(100) | NOT NULL |
|apellidos | varchar(100) | NOT NULL |
|correo | varchar(254) | opcional |
|activo | boolean | NOT NULL |
|creado_en | timestamptz | NOT NULL |
|grupo_id | bigint | FK → students_grupo(id), ON DELETE PROTECT |

### 3.2.3. questionnaires_cuestionario

| Columna | Tipo | Restricciones |
|---|---|---|
| id | bigint | PK |
| titulo | varchar(150) | NOT NULL |
| descripcion | text | opcional |
| instrucciones | text | opcional |
| tipo | varchar(20) | CHECK en ('VARK','PERSONALIDAD') |
| activo | boolean | NOT NULL |
| creado_en | timestamptz | NOT NULL |

### 3.2.4. questionnaires_pregunta

|Columna | Tipo | Restricciones |
|---|---|---|
| id | bigint | PK |
| texto | text | NOT NULL |
| orden | integer | NOT NULL |
| cuestionario_id | bigint | FK → questionnaires_cuestionario(id), ON DELETE CASCADE |
| — | — | UNIQUE(cuestionario_id, orden) |

## 3.2.5. questionnaires_opcion

| Columna | Tipo | Restricciones |
|---|---|---|
| id | bigint | PK |
| texto | text | NOT NULL |
| dimension | varchar(1) | CHECK en ('V','A','R','K','E','I','S','N','T','F','J','P') |
| orden| integer | NOT NULL |
| pregunta_id | bigint | FK → questionnaires_pregunta(id), ON DELETE CASCADE |
| — | — | UNIQUE(pregunta_id, orden) |

## 3.2.6. assessments_evaluacion

| Columna | Tipo | Restricciones |
|---|---|---|
| id | bigint | PK |
| estado | varchar(20) | CHECK en ('EN_PROGRESO','FINALIZADA') |
| iniciada_en | timestamptz | NOT NULL |
| finalizada_en | timestamptz | opcional |
| cuestionario_id | bigint | FK → questionnaires_cuestionario(id), PROTECT |
| estudiante_id | bigint | FK → students_estudiante(id), PROTECT |

## 3.2.7. assessments_respuesta

| Columna | Tipo | Restricciones |
|---|---|---|
| id | bigint | PK |
| evaluacion_id | bigint | FK → assessments_evaluacion(id), CASCADE |
| pregunta_id | bigint | FK → questionnaires_pregunta(id), PROTECT |
| — | — | UNIQUE(evaluacion_id, pregunta_id) |

## 3.2.8. assessments_seleccionrespuesta

| Columna | Tipo | Restricciones |
|---|---|---|
| id | bigint | PK |
| puntos | smallint | opcional, CHECK >= 0 |
| opcion_id | bigint | FK → questionnaires_opcion(id), PROTECT |
| respuesta_id | bigint | FK → assessments_respuesta(id), CASCADE |
| — | — | UNIQUE(respuesta_id, opcion_id) |

## 3.2.9. results_resultado

| Columna | Tipo | Restricciones |
|---|---|---|
| id | bigint | PK |
| preguntas_contestadas | integer | NOT NULL, >= 0 |
| preguntas_omitidas | integer | NOT NULL, >= 0 |
| interpretacion | text | opcional |
| calculado_en | timestamptz | NOT NULL |
| evaluacion_id | bigint | FK UNIQUE → assessments_evaluacion(id), CASCADE |

## 3.2.10. results_puntajedimension

| Columna | Tipo | Restricciones |
|---|---|---|
|id | bigint | PK |
|dimension | varchar(1) | CHECK en las 12 dimensiones |
|puntaje | integer | NOT NULL, >= 0 |
|resultado_id | bigint | FK → results_resultado(id), CASCADE |
| — | — | UNIQUE(resultado_id, dimension) |

## 3.3. Restricciones globales

- PROTECT en estudiante.grupo, evaluacion.estudiante, evaluacion.cuestionario, respuesta.pregunta y seleccion.opcion evita borrados accidentales en cascada.
- CASCADE en respuesta.evaluacion, seleccion.respuesta, resultado.evaluacion, puntaje.resultado, pregunta.cuestionario y opcion.pregunta.
- UNIQUE garantiza:
-- (cuestionario, orden) y (pregunta, orden): sin posiciones repetidas.
-- (evaluacion, pregunta): sin respuestas duplicadas.
-- (respuesta, opcion): sin selecciones repetidas.
-- (resultado, dimension): sin puntajes duplicados.
-- evaluacion en resultado: un resultado vigente por intento.

## 3.4. Script SQL equivalente (extracto)

CREATE TABLE students_grupo (
  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  clave VARCHAR(20) NOT NULL UNIQUE,
  nombre VARCHAR(100) NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  creado_en TIMESTAMPTZ NOT NULL
);

CREATE TABLE students_estudiante (
  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  matricula VARCHAR(30) NOT NULL UNIQUE,
  nombres VARCHAR(100) NOT NULL,
  apellidos VARCHAR(100) NOT NULL,
  correo VARCHAR(254),
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  creado_en TIMESTAMPTZ NOT NULL,
  grupo_id BIGINT NOT NULL REFERENCES students_grupo(id) ON DELETE PROTECT
);