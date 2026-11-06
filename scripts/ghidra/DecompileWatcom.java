// SPDX-License-Identifier: Apache-2.0
// Decompila funzioni Watcom di un ELF i386 dopo aver dichiarato la convenzione __watcall.
// Argomenti dello script: <file spec> <file di uscita>.
// Spec, righe separate da tab: T|C <simbolo> <void|value> <parametro,parametro,...>
// oppure I <simbolo> <argomenti sullo stack>: funzione senza prototipo, la firma la ricava il decompilatore.
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
import ghidra.program.model.pcode.FunctionPrototype;
import ghidra.program.model.pcode.HighFunction;
import ghidra.program.model.pcode.HighSymbol;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.PcodeOpAST;
import ghidra.program.model.pcode.Varnode;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

public class DecompileWatcom extends GhidraScript {
    private static final int MAX_STACK_ARGS = 16;

    /** Il chiamato toglie i propri argomenti: un modello per ogni numero di argomenti sullo stack, cosi' Ghidra non perde l'altezza dello stack. */
    private static String watcallXml(int stackArgs) {
        return "<prototype name=\"__watcall" + stackArgs + "\" extrapop=\"" + (4 + stackArgs * 4) + "\" stackshift=\"4\">"
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
        + "<register name=\"ESI\"/><register name=\"EDI\"/><register name=\"EBP\"/><register name=\"ESP\"/>"
        + "</unaffected>"
        + "</prototype>";
    }

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
        f.updateFunction("__watcall" + Math.max(0, params.size() - 4), ret, params, FunctionUpdateType.DYNAMIC_STORAGE_ALL_PARAMS, true,
            SourceType.USER_DEFINED);
    }

    /** Argomenti e ritorno dal corpo della funzione; la firma viene fissata cosi' anche i chiamanti la vedono. */
    private String infer(Function f, String name, int stackArgs, DecompInterface decompiler) throws Exception {
        f.setCallingConvention("__watcall" + stackArgs);
        DecompileResults r = decompiler.decompileFunction(f, 60, monitor);
        if (!r.decompileCompleted()) {
            return null;
        }
        FunctionPrototype prototype = r.getHighFunction().getFunctionPrototype();
        int count = stackArgs > 0 ? 4 + stackArgs : Math.min(prototype.getNumParams(), 4);
        boolean isVoid = prototype.getReturnType() == null || prototype.getReturnType() instanceof VoidDataType;
        StringBuilder params = new StringBuilder();
        for (int i = 0; i < count; i++) {
            params.append(i == 0 ? "" : ",").append("a").append(i + 1);
        }
        apply(f, new String[] {"C", name, isVoid ? "void" : "value", params.toString()});
        return name + " " + count + " " + (isVoid ? "void" : "value");
    }

    /** Larghezza reale degli accessi in memoria: la dimensione del simbolo non basta per i `_DAT_`. */
    private void printAccesses(HighFunction high, PrintWriter out) {
        Iterator<PcodeOpAST> ops = high.getPcodeOps();
        while (ops.hasNext()) {
            PcodeOp op = ops.next();
            int opcode = op.getOpcode();
            if ((opcode == PcodeOp.STORE || opcode == PcodeOp.LOAD) && op.getInput(1).isConstant()) {
                Varnode value = opcode == PcodeOp.STORE ? op.getInput(2) : op.getOutput();
                out.println("//@@@ACCESS " + op.getInput(1).getOffset() + " " + value.getSize());
            }
            printDirect(op.getOutput(), out);
            for (Varnode input : op.getInputs()) {
                printDirect(input, out);
            }
        }
    }

    private void printDirect(Varnode node, PrintWriter out) {
        if (node != null && node.getAddress().getAddressSpace().isLoadedMemorySpace()) {
            out.println("//@@@ACCESS " + node.getOffset() + " " + node.getSize());
        }
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        List<String> lines = Files.readAllLines(Paths.get(args[0]));
        SpecExtension extension = new SpecExtension(currentProgram);
        for (int stackArgs = 0; stackArgs <= MAX_STACK_ARGS; stackArgs++) {
            extension.addReplaceCompilerSpecExtension(watcallXml(stackArgs), monitor);
        }

        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        List<Function> targets = new ArrayList<>();
        List<String[]> toInfer = new ArrayList<>();
        for (String line : lines) {
            String[] spec = line.split("\t", -1);
            if (spec[0].equals("I")) {
                toInfer.add(spec);
                continue;
            }
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

        List<String> inferred = new ArrayList<>();
        for (String[] spec : toInfer) {
            Function f = resolve(spec[1]);
            String signature = f == null ? null : infer(f, spec[1], Integer.parseInt(spec[2]), decompiler);
            if (signature != null) {
                inferred.add(signature);
            }
        }
        try (PrintWriter out = new PrintWriter(args[1], "UTF-8")) {
            for (String signature : inferred) {
                out.println("//@@@INFER " + signature);
            }
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
                printAccesses(high, out);
                out.println(r.getDecompiledFunction().getC());
            }
        }
        decompiler.dispose();
    }
}
