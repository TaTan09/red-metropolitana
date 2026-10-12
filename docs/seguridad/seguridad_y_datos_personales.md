# Seguridad y datos personales (3.3)

## 1. Credenciales fuera de Git

PostgreSQL y Kafka reciben configuración por variables de entorno y `.env` local, ignorado por Git; sólo `.env.example` contiene valores de plantilla. No versionar contraseñas, tokens, Raw, `dbt/target` ni `dbt/logs`. La macro HMAC interpola la clave en SQL compilado: esos artefactos deben permanecer locales. Esto evita publicar accesos y datos personales accidentalmente.

## 2. Seudonimización antes de Gold

Silver conserva llaves operativas. `bridge_identidad_usuario` genera `usuario_canonico_id` como `USR-########`, `AM-<hash>` aislado o fallback `SIN-TARJETA-<md5>`; **no aplica SHA-256 salteado a tarjetas**. Features Silver conservan ese ID enlazable y requieren acceso restringido.

Gold produce `usuario_sk` con **HMAC-SHA256** y la variable privada estable `GOLD_PSEUDONYM_KEY`, mediante `dbt/red_metropolitana/macros/usuario_sk.sql`. Las vistas de multimodalidad/transbordos son agregadas y no exponen usuario individual. Seudonimizar permite joins sin publicar tarjetas, pero no anonimiza ni elimina el riesgo de inferir rutinas. La identidad persona-a-persona de Aerómetro con otros modos no puede medirse.

## 3. Quién debe ver qué (RBAC)

| Perfil | Acceso objetivo y justificación |
|---|---|
| Público | Indicadores agregados sin detalle individual: transparencia |
| BI / Planeación | Vistas Gold agregadas: demanda y cobertura |
| Ciencia de Datos | Features Silver autorizadas: modelado; identidad enlazable restringida |
| Auditoría / Seguridad | Bronze/Silver/puente: investigación con trazabilidad |
| Pipeline / dbt | Escritura de capas con `red_user`: operación local |

Estado real: `tableau_ro` tiene CONNECT, USAGE Gold, SELECT actual y default privileges del propietario dbt; se verificó la denegación Staging/Silver. Se creó **NOLOGIN**, sin inventar contraseña. Habilitarlo requiere `TABLEAU_RO_PASSWORD` externo y cambiar Tableau manualmente. El workbook sigue usando `red_user`, con acceso más amplio, y se conservó intacto. Los permisos del rol cubren todo Gold, incluidos hechos seudonimizados; usar vistas es la política BI. Los demás perfiles son política objetivo, no roles implementados. La [guía técnica](tableau_ro.md) detalla el provisionamiento reproducible y sus límites.

## 4. Retención

Política objetivo: conservar detalle individual Bronze/Silver hasta **12 meses calendario** para estudiar estacionalidad y después depurarlo mediante autorización, manteniendo agregados históricos pertinentes. No se atribuye este plazo a una norma legal ni se afirma una purga automática implementada. Al aplicarlo deben revisarse también hechos individualizados Gold y respaldos. No se eliminaron datos durante esta revisión.
