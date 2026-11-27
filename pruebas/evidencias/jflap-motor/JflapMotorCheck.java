import automata.Automaton;
import automata.AutomatonSimulator;
import automata.SimulatorFactory;
import automata.State;
import automata.Transition;
import automata.fsa.FiniteStateAutomaton;
import automata.fsa.FSATransition;
import file.XMLCodec;

import java.io.File;
import java.io.Serializable;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/** Headless conformance runner that calls JFLAP 7.1's XML reader and FSA simulator. */
public final class JflapMotorCheck {
    private record Case(String input, boolean expected) {}
    private record FileCases(String name, String machineType, List<Case> cases) {}

    private static final List<FileCases> SUITE = List.of(
        new FileCases("PRODUCTO_AFND.jff", "AFND", List.of(
            new Case("POLLO", true), new Case("PIZZA", false))),
        new FileCases("PRODUCTO_AFD.jff", "AFD", List.of(
            new Case("POLLO", true), new Case("PIZZA", false))),
        new FileCases("CANTIDAD_AFND.jff", "AFND", List.of(
            new Case("12", true), new Case("0", true), new Case("١", false), new Case("²", false))),
        new FileCases("CANTIDAD_AFD.jff", "AFD", List.of(
            new Case("12", true), new Case("0", true), new Case("١", false), new Case("²", false))),
        new FileCases("PAGO_AFND.jff", "AFND", List.of(
            new Case("YAPE", true), new Case("BITCOIN", false))),
        new FileCases("PAGO_AFD.jff", "AFD", List.of(
            new Case("YAPE", true), new Case("BITCOIN", false)))
    );

    private JflapMotorCheck() {}

    public static void main(String[] args) throws Exception {
        if (args.length != 5) {
            System.err.println("Uso: JflapMotorCheck <raiz-proyecto> <version-jar> <sha256> <reporte.json> <tabla.md>");
            System.exit(2);
        }
        Path root = Path.of(args[0]);
        String jarVersion = args[1];
        String jarSha256 = args[2];
        Path reportPath = Path.of(args[3]);
        Path tablePath = Path.of(args[4]);
        List<Map<String, Object>> files = new ArrayList<>();
        List<Map<String, Object>> results = new ArrayList<>();
        List<Map<String, Object>> pairChecks = new ArrayList<>();
        int failures = 0;

        for (FileCases fileCases : SUITE) {
            Path file = root.resolve(fileCases.name());
            Map<String, Object> fileRecord = new java.util.LinkedHashMap<>();
            fileRecord.put("file", fileCases.name());
            fileRecord.put("declaredType", fileCases.machineType());
            try {
                Serializable decoded = new XMLCodec().decode(file.toFile(), Collections.emptyMap());
                if (!(decoded instanceof FiniteStateAutomaton automaton)) {
                    throw new IllegalStateException("El XMLCodec devolvió " + decoded.getClass().getName()
                        + ", no FiniteStateAutomaton");
                }
                State initial = automaton.getInitialState();
                State[] states = automaton.getStates();
                State[] finals = automaton.getFinalStates();
                Transition[] transitions = automaton.getTransitions();
                if (initial == null) throw new IllegalStateException("No hay estado inicial");
                if (finals.length == 0) throw new IllegalStateException("No hay estados finales");
                for (Transition transition : transitions) {
                    if (!(transition instanceof FSATransition)) {
                        throw new IllegalStateException("Transición incompatible: " + transition.getClass().getName());
                    }
                }

                AutomatonSimulator simulator = SimulatorFactory.getSimulator(automaton);
                if (simulator == null) throw new IllegalStateException("SimulatorFactory devolvió null");
                fileRecord.put("loaded", true);
                fileRecord.put("readerClass", XMLCodec.class.getName());
                fileRecord.put("automatonClass", automaton.getClass().getName());
                fileRecord.put("simulatorFactory", SimulatorFactory.class.getName());
                fileRecord.put("simulatorClass", simulator.getClass().getName());
                fileRecord.put("stateCount", states.length);
                fileRecord.put("transitionCount", transitions.length);
                fileRecord.put("initialState", stateInfo(initial));
                List<Map<String, Object>> finalInfo = new ArrayList<>();
                for (State state : finals) finalInfo.add(stateInfo(state));
                fileRecord.put("finalStates", finalInfo);
                List<Map<String, Object>> stateInfo = new ArrayList<>();
                for (State state : states) stateInfo.add(stateInfo(state));
                fileRecord.put("states", stateInfo);
                List<Map<String, Object>> transitionInfo = new ArrayList<>();
                for (Transition transition : transitions) {
                    FSATransition fsa = (FSATransition) transition;
                    transitionInfo.add(Map.of(
                        "from", stateInfo(fsa.getFromState()),
                        "label", fsa.getLabel(),
                        "to", stateInfo(fsa.getToState())));
                }
                fileRecord.put("transitions", transitionInfo);

                for (Case test : fileCases.cases()) {
                    boolean accepted = simulator.simulateInput(test.input());
                    boolean passed = accepted == test.expected();
                    if (!passed) failures++;
                    Map<String, Object> result = new java.util.LinkedHashMap<>();
                    result.put("file", fileCases.name());
                    result.put("input", test.input());
                    result.put("expected", test.expected() ? "ACEPTAR" : "RECHAZAR");
                    result.put("actual", accepted ? "ACEPTAR" : "RECHAZAR");
                    result.put("passed", passed);
                    results.add(result);
                    System.out.printf("%s | %s | esperado=%s | JFLAP=%s | %s%n",
                        fileCases.name(), printable(test.input()),
                        result.get("expected"), result.get("actual"), passed ? "APROBADO" : "FALLÓ");
                }
            } catch (Throwable error) {
                failures += fileCases.cases().size();
                fileRecord.put("loaded", false);
                fileRecord.put("error", error.getClass().getName() + ": " + error.getMessage());
                for (Case test : fileCases.cases()) {
                    Map<String, Object> result = new java.util.LinkedHashMap<>();
                    result.put("file", fileCases.name());
                    result.put("input", test.input());
                    result.put("expected", test.expected() ? "ACEPTAR" : "RECHAZAR");
                    result.put("actual", "NO EJECUTADO");
                    result.put("passed", false);
                    result.put("error", error.getClass().getName() + ": " + error.getMessage());
                    results.add(result);
                    System.out.printf("%s | %s | NO EJECUTADO | ERROR: %s%n",
                        fileCases.name(), printable(test.input()), error);
                }
            }
            files.add(fileRecord);
        }

        for (String token : List.of("PRODUCTO", "CANTIDAD", "PAGO")) {
            String nfa = token + "_AFND.jff";
            String dfa = token + "_AFD.jff";
            for (Map<String, Object> nfaResult : results) {
                if (!nfa.equals(nfaResult.get("file"))) continue;
                Map<String, Object> dfaResult = results.stream()
                    .filter(row -> dfa.equals(row.get("file"))
                        && nfaResult.get("input").equals(row.get("input")))
                    .findFirst().orElse(null);
                boolean same = dfaResult != null
                    && nfaResult.get("actual").equals(dfaResult.get("actual"));
                Map<String, Object> pair = new java.util.LinkedHashMap<>();
                pair.put("token", token);
                pair.put("input", nfaResult.get("input"));
                pair.put("afnd", nfaResult.get("actual"));
                pair.put("afd", dfaResult == null ? "NO EJECUTADO" : dfaResult.get("actual"));
                pair.put("sameResult", same);
                pairChecks.add(pair);
                if (!same) failures++;
                System.out.printf("EQUIVALENCIA %s | %s | AFND=%s | AFD=%s | %s%n",
                    token, printable((String)nfaResult.get("input")), pair.get("afnd"), pair.get("afd"),
                    same ? "COINCIDE" : "DIFIERE");
            }
        }

        Map<String, Object> report = new java.util.LinkedHashMap<>();
        report.put("generatedAt", Instant.now().toString());
        report.put("javaVersion", System.getProperty("java.version"));
        report.put("javaRuntime", System.getProperty("java.runtime.version"));
        report.put("headless", java.awt.GraphicsEnvironment.isHeadless());
        report.put("jflapVersion", jarVersion);
        report.put("jflapJarSha256", jarSha256);
        report.put("readerClass", XMLCodec.class.getName());
        report.put("simulatorFactory", SimulatorFactory.class.getName());
        report.put("loadedFiles", files);
        report.put("simulations", results);
        report.put("nfaDfaCaseComparisons", pairChecks);
        report.put("summary", Map.of(
            "files", files.size(),
            "loadedFiles", files.stream().filter(f -> Boolean.TRUE.equals(f.get("loaded"))).count(),
            "simulations", results.size(),
            "passed", results.stream().filter(r -> Boolean.TRUE.equals(r.get("passed"))).count(),
            "nfaDfaComparisons", pairChecks.size(),
            "nfaDfaMismatches", pairChecks.stream().filter(r -> !Boolean.TRUE.equals(r.get("sameResult"))).count(),
            "failed", failures));
        String json = Json.write(report) + System.lineSeparator();
        Files.writeString(reportPath, json, StandardCharsets.UTF_8);
        writeTable(tablePath, results);
        System.out.printf("RESUMEN: archivos=%d, simulaciones=%d, fallidas=%d, modoHeadless=%s%n",
            files.size(), results.size(), failures, java.awt.GraphicsEnvironment.isHeadless());
        if (failures > 0) System.exit(1);
    }

    private static Map<String, Object> stateInfo(State state) {
        Map<String, Object> info = new java.util.LinkedHashMap<>();
        info.put("id", state.getID());
        info.put("name", state.getName());
        info.put("label", state.getLabel());
        return info;
    }

    private static String printable(String input) {
        return input.codePoints().mapToObj(cp -> cp > 127
            ? String.format("U+%04X", cp) : new String(Character.toChars(cp)))
            .reduce((a, b) -> a + " " + b).orElse("");
    }

    private static void writeTable(Path path, List<Map<String, Object>> results) throws Exception {
        StringBuilder table = new StringBuilder("| Archivo | Cadena | Esperado | JFLAP | Resultado |\n")
            .append("|---|---|---|---|---|\n");
        for (Map<String, Object> row : results) {
            table.append("| ").append(row.get("file")).append(" | ")
                .append(row.get("input")).append(" | ").append(row.get("expected"))
                .append(" | ").append(row.get("actual")).append(" | ")
                .append(Boolean.TRUE.equals(row.get("passed")) ? "APROBADO" : "FALLÓ").append(" |\n");
        }
        Files.writeString(path, table.toString(), StandardCharsets.UTF_8);
    }

    /** Minimal JSON serializer for maps/lists/scalars, avoiding any external dependency. */
    private static final class Json {
        static String write(Object value) {
            if (value == null) return "null";
            if (value instanceof String text) return quote(text);
            if (value instanceof Number || value instanceof Boolean) return value.toString();
            if (value instanceof Map<?, ?> map) {
                List<String> fields = new ArrayList<>();
                map.forEach((key, val) -> fields.add(quote(String.valueOf(key)) + ": " + write(val)));
                return "{\n  " + String.join(",\n  ", fields) + "\n}";
            }
            if (value instanceof Iterable<?> iterable) {
                List<String> items = new ArrayList<>();
                iterable.forEach(item -> items.add(write(item)));
                return "[" + String.join(", ", items) + "]";
            }
            return quote(value.toString());
        }

        private static String quote(String text) {
            StringBuilder out = new StringBuilder("\"");
            for (int i = 0; i < text.length(); i++) {
                char c = text.charAt(i);
                switch (c) {
                    case '"' -> out.append("\\\"");
                    case '\\' -> out.append("\\\\");
                    case '\n' -> out.append("\\n");
                    case '\r' -> out.append("\\r");
                    case '\t' -> out.append("\\t");
                    default -> { if (c < 0x20) out.append(String.format("\\u%04x", (int)c)); else out.append(c); }
                }
            }
            return out.append('"').toString();
        }
    }
}
