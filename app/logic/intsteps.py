import sympy
import collections
import stepprinter
from stepprinter import functionnames, Equals

def Rule(name, props=""):
    return collections.namedtuple(name, props + " context symbol")

ConstantRule = Rule("ConstantRule", "constant")
ConstantTimesRule = Rule("ConstantTimesRule", "constant other substep")
PowerRule = Rule("PowerRule", "base exp")
AddRule = Rule("AddRule", "substeps")
URule = Rule("URule", "substep inner innerstep")
TrigRule = Rule("TrigRule", "func arg")
ExpRule = Rule("ExpRule", "base exp")
AlternativeRule = Rule("AlternativeRule", "alternatives")
DontKnowRule = Rule("DontKnowRule")
RewriteRule = Rule("RewriteRule", "rewritten substep")

# Method based on that on SIN, described in "Symbolic Integration: The
# Stormy Decade"
def find_substitution(integrand, symbol):
    results = []

    def is_subterm(term):
        for t in integrand.args:
            difference = sympy.simplify(sympy.trigsimp(term / t))
            if difference.is_constant(symbol):
                return True
        return False

    def possible_subterms(term):
        if term.func in (sympy.sin, sympy.cos, sympy.tan,
                         sympy.asin, sympy.acos, sympy.atan,
                         sympy.exp, sympy.log, sympy.Mul):
            return term.args
        elif term.func == sympy.Pow:
            if term.args[1].is_constant(symbol):
                return [term.args[0]]
            elif term.args[0].is_constant(symbol):
                return [term.args[1]]
        return []

    for term in possible_subterms(integrand):
        if is_subterm(term.diff(symbol)):
            results.append(term)

        subterms = possible_subterms(term)
        for subterm in subterms:
            if is_subterm(subterm.diff(symbol)):
                results.append(subterm)

    return results

def intsteps(integrand, symbol):
    func = integrand.func

    if integrand.is_constant(symbol):
        return ConstantRule(integrand, func, symbol)

    elif func == sympy.Symbol:
        return PowerRule(integrand, 1, integrand, symbol)

    elif func == sympy.Pow:
        base, exp = integrand.as_base_exp()
        if exp.is_constant(symbol) and base.func == sympy.Symbol:
            return PowerRule(base, exp, integrand, symbol)

    elif func == sympy.Add:
        return AddRule([intsteps(g, symbol) for g in integrand.args],
                       integrand, symbol)

    elif func == sympy.Mul:
        args = integrand.args

        if len(args) == 2:
            if integrand.args[0].is_constant(symbol):
                return ConstantTimesRule(args[0], args[1],
                                         intsteps(args[1], symbol),
                                         integrand, symbol)
            elif integrand.args[1].is_constant(symbol):
                return ConstantTimesRule(args[1], args[0],
                                         intsteps(args[0], symbol),
                                         integrand, symbol)

    return DontKnowRule(integrand, symbol)


def intmanually(rule):
    if isinstance(rule, ConstantRule):
        return rule.constant * rule.symbol

    elif isinstance(rule, PowerRule):
        return (rule.base ** (rule.exp + 1)) / (rule.exp + 1)

    elif isinstance(rule, AddRule):
        return sum(map(intmanually, rule.substeps))

    elif isinstance(rule, ConstantTimesRule):
        return rule.constant * intmanually(rule.substep)

    return None

class IntegralPrinter(object):
    def __init__(self, rule):
        self.rule = rule
        self.print_rule(rule)

    def print_rule(self, rule):
        if isinstance(rule, ConstantRule):
            self.print_Constant(rule)
        elif isinstance(rule, ConstantTimesRule):
            self.print_ConstantTimes(rule)
        elif isinstance(rule, PowerRule):
            self.print_Power(rule)
        elif isinstance(rule, AddRule):
            self.print_Add(rule)
        elif isinstance(rule, URule):
            self.print_U(rule)
        elif isinstance(rule, TrigRule):
            self.print_Trig(rule)
        elif isinstance(rule, ExpRule):
            self.print_Exp(rule)
        elif isinstance(rule, AlternativeRule):
            self.print_Alternative(rule)
        elif isinstance(rule, DontKnowRule):
            self.print_DontKnow(rule)
        elif isinstance(rule, RewriteRule):
            self.print_Rewrite(rule)
        else:
            self.append(repr(rule))

    def print_Constant(self, rule):
        with self.new_step():
            self.append("The integral of a constant is the constant "
                        "times the variable of integration:")
            self.append(
                self.format_math_display(
                    Equals(sympy.Integral(rule.constant, rule.symbol),
                           intmanually(rule))))

    def print_ConstantTimes(self, rule):
        with self.new_step():
            self.append("The integral of a constant times a function "
                        "is the constant times the integral of the function:")
            self.append(self.format_math_display(
                Equals(
                    sympy.Integral(rule.context, rule.symbol),
                    rule.constant * sympy.Integral(rule.other, rule.symbol))))

            with self.new_level():
                self.print_rule(rule.substep)
            self.append("So, the result is: {}".format(
                self.format_math(intmanually(rule))))

    def print_Power(self, rule):
        with self.new_step():
            self.append("The integral of {} is {}:".format(
                self.format_math(rule.symbol ** sympy.Symbol('n')),
                self.format_math((rule.symbol ** (1 + sympy.Symbol('n'))) /
                                 (1 + sympy.Symbol('n')))
            ))
            self.append(
                self.format_math_display(
                    Equals(sympy.Integral(rule.context, rule.symbol),
                           intmanually(rule))))

    def print_Add(self, rule):
        with self.new_step():
            self.append("Integrate term-by-term:")
            for substep in rule.substeps:
                with self.new_level():
                    self.print_rule(substep)
            self.append("The result is: {}".format(
                self.format_math(intmanually(rule))))

    def print_DontKnow(self, rule):
        with self.new_step():
            self.append("Don't know the steps in finding this integral.")
            self.append("But the integral is")
            self.append(self.format_math_display(intmanually(rule)))


class HTMLPrinter(IntegralPrinter, stepprinter.HTMLPrinter):
    def __init__(self, rule):
        stepprinter.HTMLPrinter.__init__(self)
        IntegralPrinter.__init__(self, rule)

    def print_Alternative(self, rule):
        with self.new_step():
            self.append("There are multiple ways to do this derivative.")
            for index, r in enumerate(rule.alternatives):
                with self.new_collapsible():
                    self.append_header("Method #{}".format(index + 1))
                    with self.new_level():
                        self.print_rule(r)

    def finalize(self):
        answer = intmanually(self.rule)
        if answer:
            simp = sympy.simplify(sympy.trigsimp(answer))
            if simp != answer:
                answer = simp
                with self.new_step():
                    self.append("Now simplify:")
                    self.append(self.format_math_display(simp))
        with self.new_step():
            self.append("Add the constant of integration:")
            self.append(self.format_math_display(answer + sympy.Symbol('constant')))
        self.lines.append('</ol>')
        return '\n'.join(self.lines)

def print_html_steps(function, symbol):
    a = HTMLPrinter(intsteps(function, symbol))
    return a.finalize()
