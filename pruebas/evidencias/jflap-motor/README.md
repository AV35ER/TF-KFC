# Validación con el motor original JFLAP 7.1

El ejecutor temporal carga cada `.jff` con `file.XMLCodec.decode(File, Map)` y obtiene el simulador mediante `automata.SimulatorFactory.getSimulator(Automaton)`. Para los seis archivos FSA, la factoría selecciona `automata.fsa.FSAStepWithClosureSimulator`, que hereda el motor de simulación FSA de JFLAP. La prueba se ejecuta en modo headless; no abre ventanas y no modifica los `.jff`.

Se inspeccionaron las firmas incluidas en el JAR con `javap`; el inventario de API está en `inspeccion-api-jflap.txt`. El ejecutor no implementa lógica propia de autómatas: hace la simulación con `AutomatonSimulator.simulateInput(String)`.

## Ejecutar

Desde PowerShell en cualquier directorio:

```powershell
.pruebasevidenciasjflap-motorun-jflap-tests.ps1 -JflapJar "C:\ruta\a\JFLAP7.1.jar"
```

También se puede definir `JFLAP_JAR`. Si el proyecto está junto al workspace original `analizador-kfc-main`, el script intenta localizar allí el JAR por defecto. Java y `javac` 17 o posterior deben estar disponibles en `PATH`.

El script compila el ejecutor en un directorio temporal del sistema, lo ejecuta con `java.awt.headless=true`, elimina los `.class` temporales y deja en esta carpeta:

- `JflapMotorCheck.java`: código fuente del ejecutor.
- `run-jflap-tests.ps1`: script reproducible.
- `ejecucion-completa.log`: versiones, firmas API y salida de todas las simulaciones.
- `reporte-jflap.json`: metadatos de carga, estados, transiciones, 16 simulaciones y comparaciones AFND/AFD.
- `resultados-jflap.md`: tabla legible de los resultados.
- `inspeccion-api-jflap.txt`: firmas reales inspeccionadas con `javap`.

El nombre del archivo indica AFND/AFD. JFLAP representa ambos como `automata.fsa.FiniteStateAutomaton`; `SimulatorFactory` selecciona su simulador con cierre lambda. El manifiesto del JAR no contiene un campo de versión, por eso el reporte consigna la distribución por su nombre `JFLAP7.1.jar` y además su SHA-256.
