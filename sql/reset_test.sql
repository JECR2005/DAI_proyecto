-- Deja vacía la base modulab_test para las pruebas de integración.
-- Se ejecuta con el usuario administrador (sql/crear_base.py --reset-test).
DELETE FROM dbo.perfiles_historial;
DELETE FROM dbo.perfiles;
DELETE FROM dbo.conversaciones;
DELETE FROM dbo.trazas;
DELETE FROM dbo.cotizaciones_emitidas;
DELETE FROM dbo.solicitudes_especiales;
ALTER SEQUENCE dbo.seq_folios RESTART WITH 1;
GO
