# Prueba de Universal Animation Library

Rama aislada: `feat/quaternius-animations`. Mantener main y el servidor 8000 intactos.

1. Conservar la edición Standard sin root motion y su licencia CC0 como fuente reproducible.
2. Convertir offline las rotaciones globales del rig Quaternius al rig original de 18 huesos, corrigiendo T-pose/A-pose y diferencias de jerarquía. Eliminar desplazamiento horizontal; saltos controlados por física.
3. Sustituir locomoción, puñetazos, reacción y conjuro por clips retargeteados. Conservar guardias, patadas, poderes exclusivos y remates originales. Sin cambios al protocolo de modelos ni reglas.
4. Permitir comparar con la versión original mediante `?animations=original`; Quaternius por defecto en esta rama. Añadir un visor independiente con personaje, clip y pausa para inspección.
5. Verificar reproducción, huesos finitos, límites de movimiento, activos locales, build, regresión de combate y navegador. Publicar la rama y levantar una vista previa aislada.

Los ataques se muestrean con el progreso autoritativo del servidor. No se usan temporizadores de animación para producir daño. El paquete gratuito contiene 43 clips; no contiene todas las técnicas de un juego de lucha.
