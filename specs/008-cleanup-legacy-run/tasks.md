# Tasks - Spec 008: Limpieza de Ejecución Legada Single-Run

## Implementación completada

- [x] Remover `_RUNTIME_CONTRACT_KEYS` de `main.py`
- [x] Remover `_has_runtime_contract_env()` de `main.py`
- [x] Remover función `_run_run()` completa de `main.py`
- [x] Remover condición `if args.command_name == "run"` de `app()`
- [x] Remover parser "run" de `_build_parser()`
- [x] Remover imports legados: `ContainerInstantiation`, `RunInput`, `prepare_target_repository`, `run_agent_baseline`
- [x] Actualizar `tests/test_main.py`: remover 4 tests de `_run_run()`
- [x] Crear nuevos tests para `batch` command y `_run_batch()`
- [x] Crear spec 008 con documentación

## Validación pendiente

- [ ] `make lint` en verde
- [ ] `make typecheck` en verde
- [ ] Tests unitarios: `python -m unittest tests.test_main`
- [ ] Verificar que `autofix batch` aún funciona con batch config sample
