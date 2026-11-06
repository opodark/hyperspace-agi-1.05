// SPDX-License-Identifier: Apache-2.0
// Decompila funzioni Watcom di un ELF i386 dopo aver dichiarato la convenzione __watcall.
// Argomenti dello script: <file spec> <file di uscita>.
// Spec, righe separate da tab: T|C <simbolo> <void|value> <parametro,parametro,...>
//@category HyperSpace

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.database.SpecExtension;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.Undefined4DataType;
import ghidra.program.model.data.VoidDataType;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Function.FunctionUpdateType;
import ghidra.program.model.listing.Parameter;
import ghidra.program.model.listing.ParameterImpl;
import ghidra.program.model.listing.ReturnParameterImpl;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.pcode.HighFunction;
import ghidra.program.model.pcode.HighSymbol;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

public class DecompileWatcom extends GhidraScript {
    private static final String WATCALL_XML =
        "<prototype name=\"__watcall\" extrapop=\"unknown\" stackshift=\"4\">"
        + "<input>"
        + "<pentry minsize=\"1\" maxsize=\"4\"><register name=\"EAX\"/></pentry>"
        + "<pentry minsize=\"1\" maxsize=\"4\"><register name=\"EDX\"/></pentry>"
        + "<pentry minsize=\"1\" maxsize=\"4\"><register name=\"EBX\"/></pentry>"
        + "<pentry minsize=\"1\" maxsize=\"4\"><register name=\"ECX\"/></pentry>"
        + "<pentry minsize=\"1\" maxsize=\"500\" align=\"4\"><addr offset=\"4\" space=\"stack\"/></pentry>"
        + "</input>"
        + "<output><pentry minsize=\"1\" maxsize=\"4\"><register name=\"EAX\"/></pentry></output>"
        + "<unaffected>"
        + "<register name=\"EBX\"/><register name=\"ECX\"/><register name=\"EDX\"/>"
        + "<register name=\"ESI\"/><register name=\"EDI\"/><register name=\"EBP\"/>"
        + "</unaffected>"
        + "</prototype>";

    private Function resolve(String name) throws Exception {
        for (Symbol s : currentProgram.getSymbolTable().getSymbols(name)) {
            Object o = s.getObject();
            if (o instanceof Function) {
                return (Function) o;
            }
            if (!s.isExternal()) {
                Address a = s.getAddress();
                disassemble(a);
                Function f = createFunction(a, name);
                if (f != null) {
                    return f;
                }
            }
        }
        return null;
    }

    private void apply(Function f, String[] spec) throws Exception {
        List<Parameter> params = new ArrayList<>();
        if (spec.length > 3 && !spec[3].isEmpty()) {
            for (String p : spec[3].split(",")) {
                params.add(new ParameterImpl(p, Undefined4DataType.dataType, currentProgram));
            }
        }
        ReturnParameterImpl ret = new ReturnParameterImpl(
            spec[2].equals("void") ? VoidDataType.dataType : Undefined4DataType.dataType, currentProgram);
        f.updateFunction("__watcall", ret, params, FunctionUpdateType.DYNAMIC_STORAGE_ALL_PARAMS, true,
            SourceType.USER_DEFINED);
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        List<String> lines = Files.readAllLines(Paths.get(args[0]));
        new SpecExtension(currentProgram).addReplaceCompilerSpecExtension(WATCALL_XML, monitor);

        List<Function> targets = new ArrayList<>();
        for (String line : lines) {
            String[] spec = line.split("\t", -1);
            Function f = resolve(spec[1]);
            if (f == null) {
                println("SIMBOLO NON TROVATO: " + spec[1]);
                continue;
            }
            apply(f, spec);
            if (spec[0].equals("T")) {
                targets.add(f);
            }
        }

        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        try (PrintWriter out = new PrintWriter(args[1], "UTF-8")) {
            MemoryBlock fake = currentProgram.getMemory().getBlock(".hsext");
            if (fake != null) {
                for (Symbol sym : currentProgram.getSymbolTable().getAllSymbols(false)) {
                    if (fake.contains(sym.getAddress())) {
                        out.println("//@@@SYM " + sym.getName() + " " + sym.getAddress().getOffset());
                    }
                }
            }
            for (Function f : targets) {
                DecompileResults r = decompiler.decompileFunction(f, 180, monitor);
                out.println("//@@@ " + f.getName());
                if (!r.decompileCompleted()) {
                    out.println("// ERRORE: " + r.getErrorMessage());
                    continue;
                }
                HighFunction high = r.getHighFunction();
                Iterator<HighSymbol> globals = high.getGlobalSymbolMap().getSymbols();
                while (globals.hasNext()) {
                    HighSymbol g = globals.next();
                    if (g.getDataType() != null) {
                        out.println("//@@@GLOBAL " + g.getName() + " " + g.getDataType().getLength());
                    }
                }
                out.println(r.getDecompiledFunction().getC());
            }
        }
        decompiler.dispose();
    }
}
