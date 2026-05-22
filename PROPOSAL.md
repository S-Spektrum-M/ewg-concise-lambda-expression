---
title: "Concise Lambda Expressions"
document: PXXXXR0
date: 2026-05-12
audience:
  - EWGI
  - EWG
author:
  - name: Siddharth Mohanty
    email: <smohanty22@andrew.cmu.edu>
toc: true
---

# Revision History

N/A.

# Abstract

This paper proposes a concise lambda expression syntax of the form
`(params) => expr`, which lowers to a captureless generic lambda whose
parameters default to forwarding references and whose return type is deduced
via standard `auto` rules. The syntax is purely additive: it introduces a
new token (`=>`) and a new production in *primary-expression*, leaves the
existing lambda grammar untouched, and provides no facility for capture.

Captureless single-expression lambdas are by a substantial margin the most
common shape of lambda observed in modern C++ codebases. For instance, an
empirical analysis of the LLVM codebase reveals that 22.61% of all lambda functions
(nearly 1 in 4) are captureless and single-expression. Particularly in
range pipelines, algorithm calls, and projection arguments, the
syntactic overhead of the current form is disproportionate to their
semantic weight.

# Motivation

The C++ lambda has matured into the de facto unit of local function
abstraction, but the syntactic weight of the construct has not changed
since C++11. A simple squaring callable is:

```cpp
[](auto&& x) { return x * x; };
```

The same callable in JavaScript, C#, Scala, Kotlin, and several other
contemporary languages is `(x) => x * x` or `x => x * x`.

The C++ form contains 18 characters of syntactic scaffolding including:

- Capture brackets (for a captureless pure function).
- Parameter type (in a declaration where the type would be automatically inferred anyway).
- The `return` keyword and surrounding braces (in a single expression function).

For range pipelines this overhead is amplified, since lambdas tend to
appear several times per pipeline:

```cpp
auto result = v
            | views::filter([](auto&& x) { return x > 0; })
            | views::transform([](auto&& x) { return x * x; })
            | views::take_while([](auto&& x) { return x < 100; });
```

versus the proposed:

```cpp
auto result = v
            | views::filter((x) => x > 0)
            | views::transform((x) => x * x)
            | views::take_while((x) => x < 100);
```

The existing form obscures the pipeline actions behind lambda syntax. By
dropping the lambda syntax, the pipeline achieves a higher signal-noise ratio.

This proposal targets the most-common, most-needed form—a captureless,
single-expression callable—which deserves first-class syntax.

Cases that require capture, multiple statements, explicit return types, template
parameter lists, or `mutable`/`consteval`/`static` operators continue to be
expressible via the existing *lambda-expression* syntax.

# Proposal

## Syntax

A new *concise-lambda-expression* production is added to
*primary-expression*:

> | _concise-lambda-expression:_
> |     `(` _concise-lambda-parameter-list~opt~_ `)` `=>` _assignment-expression_
>
> | _concise-lambda-parameter-list:_
> |     _concise-lambda-parameter_
> |     _concise-lambda-parameter-list_ `,` _concise-lambda-parameter_
>
> | _concise-lambda-parameter:_
> |     _identifier_
> |     _parameter-declaration_

A new token `=>` is introduced. It is otherwise unused in the grammar.

## Semantics

A `concise-lambda-expression` of the form `(p_1, ..., p_N) => E` is
equivalent to the `lambda-expression`:

```cpp
[] (P_1, ..., P_N) -> auto { return E; }
```

where each `P_i` is determined from `p_i` as follows:
- If `p_i` is an identifier `x` with no accompanying `decl-specifier-seq`, then `P_i` is `auto&& x`.
- If `p_i` is a `parameter-declaration`, `P_i` is `p_i` unchanged.

The lambda has no `lambda-capture` and no `lambda-specifier-seq`. The
resulting closure type is implicitly `constexpr`-callable wherever a
captureless lambda of the corresponding equivalent form would be.

## Examples

```cpp
auto square    = (x) => x * x;              // [] (auto&& x) { return x * x; }
auto add       = (x, y) => x + y;           // [] (auto&& x, auto &&y) {return x + y};
auto identity  = (x) => x;                  // [] (auto &&x) -> auto {return x;}
                                            // returns a copy
auto greet     = () => std::puts("hi");     // returns int (the result of puts)

// Mixing inferred and explicit parameter forms
auto clamp_pos = (int x) => x < 0 ? 0 : x;
auto project_value = (const auto& db, y) => db[y];
```

```cpp
// In a pipeline
auto names = people
           | views::filter((p) => p.age >= 18)
           | views::transform((p) => p.name);

// As a projection / comparator
std::ranges::sort(employees, std::less{}, (e) => e.hire_date);

// With std::visit
std::visit(overloaded{
    (int  i) => handle_int(i),
    (auto& x) => handle_default(x),
}, v);
```

## Restrictions

A *concise-lambda-expression* shall not: introduce a *lambda-capture*;
declare a return type explicitly; declare a template parameter list;
apply `mutable`, `static`, `consteval`, `constexpr`, or other `lambda-specifier`s;
use a `requires-clause`; or contain a `compound-statement` body — the body
is a single *assignment-expression*.

Code requiring any of these continues to use the existing
*lambda-expression* form.

# Discussion

## Why no Captures

The single most common source of subtle bugs in lambda-heavy code is
implicit capture of references that outlive their referent.

Mandating an empty capture list at the syntactic level converts an entire
class of dangling-reference bugs into a syntactic refusal. If the body of the
concise lambda would have required a capture, the compiler diagnoses an
unrelated lookup failure for the named entity and the user falls back to
the explicit form.

Concise lambdas may, of course, reference entities with linkage —
globals, statics, member functions of an enclosing class via `this` from
the surrounding context being unavailable (since `this` is itself a
capture). For lambdas inside member functions that need `this`, the
existing lambda form remains.

## `auto` Return Type

The concise lambda lowers to an implicit `auto` return type, exactly as standard lambdas do. This strips references
and cv-qualifiers, yielding by-value returns.

We strongly considered `decltype((E))` and `decltype(auto)` to preserve reference categories, but both create
catastrophic dangling reference traps when combined with `auto&&` parameters. For example, given the projection
`auto get_name = (e) => e.name;`, if the caller passes an rvalue (e.g., yielding from a view), the parameter
`e` deduces as an rvalue reference. However, the expression `e.name` is an lvalue. If the lambda's return type were
deduced via `decltype((E))` or `decltype(auto)`, it would evaluate to `std::string&`, returning a dangling reference
to a subobject of a destroyed temporary.

By defaulting to `auto`, the concise lambda safely returns a copy.
This is the correct default for the vast majority of use cases
(predicates, simple mathematical transforms, and ranges projections). Users who explicitly need to return a
reference (e.g., to build a custom view) must fall back to the explicit lambda syntax
`[](auto&& x) -> auto& { return x.name; }`. The concise syntax prioritizes safety and predictability over completeness.

## Why `auto&&` for Inferred Parameters

The default parameter type is `auto&&`. This acts as a forwarding reference, allowing the lambda to bind to prvalues, lvalues, const, and non-const arguments without ever incurring an implicit copy at the parameter boundary.

There are three plausible candidates for the default:

  - **`auto`** silently copies. A concise lambda of the form
    `(p) => p.size()` applied to a `std::string` would copy the string
    per invocation. Under range-pipeline composition — the headline use
    case — this cost compounds across every stage.

  - **`const auto&`** binds safely, but rejects mutable algorithms. The
    expression `(x) => ++x` becomes ill-formed not because of the user's
    logic, but because the rewrite inserted an unwritten cv-qualifier.

  - **`auto&&`** is the only form that universally binds to the caller's
    argument without copying and without imposing unrequested constness.

Crucially, while `auto&&` accepts arguments transparently, the parameter itself is evaluated as an lvalue within the body `E` (as all named variables are in C++). We do not attempt implicit perfect forwarding (e.g., wrapping usages in `std::forward`). If a user needs to perfectly forward the value category of the argument to an overloaded function inside the body, they should use the explicit lambda syntax. For the vast majority of concise lambda use cases—member access, operators, and by-value transformations—the lvalue evaluation of the `auto&&` parameter is exactly what is required.

When the user wants something else — `int`, `const std::string&`,
`auto` by value — they write the full *parameter-declaration*. This is
the second axis of the proposal: types are *optional but available*. A
user who wants by-value semantics writes `(auto x) => ...`; a user who
wants const-lvalue semantics writes `(const auto& x) => ...`. Both are
two characters longer than the bare-identifier form and immediately
self-documenting at the point of use.

## Why Parentheses Are Required Around the Parameter List

The bare-identifier form, `x => x * x`, is admitted by JavaScript and
C#. We considered it and rejected it for C++ for parsing reasons
(see [Parsing considerations]). The cost is two characters in the
single-parameter case, which we judge acceptable in exchange for a
strictly LR-parseable grammar addition.

## Static Call Operator

C++23 added the ability to declare a lambda's call operator `static`,
eliminating the implicit object parameter at the call site. Concise
lambdas are captureless and therefore would suffer no semantic change
from being defined with a `static` call operator. We considered this and
chose to lower to a non-`static` call operator, on the grounds that:

  1. The closure type of a concise lambda is otherwise indistinguishable
     from the closure type of its explicit-form equivalent, which is
     valuable for refactoring (a user converting between the two forms
     should not encounter a silent type change).
  2. The benefit of a `static` operator is measurable but small, and the
     existing form remains available for users who want it.

This is, however, a defensible alternative design and is called out
explicitly for committee consideration.

## `noexcept` Semantics

Because concise lambdas omit the `lambda-specifier-seq`, they cannot be explicitly marked `noexcept`. We considered specifying that concise lambdas implicitly deduce their exception specification (i.e., lowering to `noexcept(noexcept(E))`).

We rejected this to maintain strict equivalence with explicit lambdas. Standard lambdas do not implicitly deduce `noexcept`. If a user refactors a concise lambda into an explicit lambda to add a capture, the closure type's properties should not silently degrade. Users requiring a strict `noexcept` callable must use the explicit lambda form.

## Interaction With `constexpr`

Concise lambdas are implicitly `constexpr` under exactly the same
conditions as captureless explicit lambdas — i.e., always, modulo the
constexpr-eligibility of `E`. No additional rule is required; this
follows from the rewriting in [Semantics].

## Attributes

It is not yet settled whether attributes should be permitted on concise lambda
parameters (e.g., `([[maybe_unused]] x) => x`) or on the generated call operator.
Because this syntax omits the `lambda-specifier-seq`, standard placement for
operator attributes (like `[[nodiscard]]`) is unavailable. Attributes applied
to the *primary-expression* containing the lambda do not appertain to the
generated `operator()`. We intend to seek EWG feedback on whether to extend
the grammar to explicitly support attributes or to leave them unsupported for
this minimal syntax.

# Parsing Considerations

The most significant question for this proposal is whether the syntax
can be parsed without ambiguity or unbounded look ahead. The concern is
that `(x)` — at the start of an expression context — is already a valid
parenthesized expression, and `(int)` is a valid type-id in a cast
expression. The proposed grammar adds *another* interpretation: a
concise-lambda parameter list.

The disambiguator is the `=>` token. After consuming a matched `(` … `)`
in an expression context, the parser examines the next token:

  - If it is `=>`, the construct is a *concise-lambda-expression*. The
    contents of the parentheses are re-parsed (or were tentatively
    parsed) as a *concise-lambda-parameter-list*.
  - Otherwise, the construct is whatever it would have been without this
    proposal (parenthesized expression, function-style cast, etc.).

While finding the matching close parenthesis requires scanning ahead an
arbitrary number of tokens (to skip over nested parentheses and templates),
the look ahead is bounded syntactically by the balancing of parentheses.
Most production C++ parsers (Clang, EDG, MSVC, GCC) already perform
tentative parsing of comparable complexity to disambiguate
declaration-vs-expression at function scope (e.g., the
`T(x);`-could-be-declaration-or-expression case). The implementation
cost is concretely small.

The `=>` token itself is novel. The lexer must be extended to recognize
it; under the maximal-munch rule, this requires no change to the
treatment of `=` or `>` in any other context, because `=>` never arises
in existing well-formed C++. There is, in particular, no conflict with
the spaceship operator `<=>`, since `<=>` is lexed as a single token
under existing rules and `=>` cannot appear as a suffix of `<=>` in any
grammar production.

A residual concern is recovery: when the user writes a malformed
parameter list followed by `=>`, the parser must produce a diagnostic
that points at the parameter list rather than reporting "unexpected
`=>`" at the body. The recommended strategy is to commit to the
concise-lambda interpretation as soon as `=>` is seen and re-diagnose
the parenthesized contents in that mode.

# Prior Art

Abbreviated-lambda proposals have appeared periodically in the WG21
record; [@P0573] in particular proposed a `=>` form for abbreviating
the lambda body while retaining the `[]` introducer and full parameter
list. That proposal was not adopted, with EWG feedback concentrating on
the addition of a second body form to an already-complex lambda
grammar.

This proposal differs along three significant axes:

  1. **No `[]` introducer.** The `[capture-list]` syntax is the most
     visually distinctive — and most syntactically expensive — part of
     the current lambda. Removing it entirely (rather than allowing
     `[]` to be elided) makes the new form clearly distinct from the
     existing one rather than a shorter spelling of it.
  2. **No captures, by design.** This is a feature, not a limitation;
     see [Why no captures].
  3. **Parameter types are optional.** The user opts into specificity
     rather than opting out of verbosity.

The result is a construct that is closer in spirit to mathematical
function notation and to the lambda forms of contemporary high-level
languages, while remaining a strict subset of what the existing C++
lambda can express.

# Impact on existing code

None. The proposed feature is purely additive. The `=>` token does not
appear in any well-formed C++ program prior to this proposal; the new
grammar production is reachable only via the new token. No existing
lambda syntax, semantics, or closure-type properties are changed.

ABI is unaffected: a concise lambda lowers to an explicit lambda whose
ABI is already specified.

# Empirical Analysis: LLVM Codebase Study

To evaluate the assertion that captureless, single-expression lambdas are the dominant form of lambdas in modern C++, we conducted an empirical analysis on the **LLVM** codebase (specifically, the `llvm-project` mono-repo).

LLVM represents a large-scale, performance-critical C++ project containing extensive modern C++ usage (e.g., standard library algorithms, range adapters, and projections).

A custom lexical parser scanned **55,374 C++ source and header files** in LLVM to classify all C++ lambda expressions based on their captures and body complexity.

## Findings

The analysis discovered a total of **43,336 lambda expressions**. The results are categorized as follows:

| Metric | Count | Percentage |
| :--- | :--- | :--- |
| **Total Lambdas Found** | **43,336** | **100.00%** |
| **Captureless Lambdas (`[]`)** | **15,612** | **36.03%** |
| **Captureless Single-Expression Lambdas** | **9,799** | **22.61%** of all lambdas |
| **Single-Expression % of Captureless** | **9,799 / 15,612** | **62.77%** of captureless lambdas |

## Analysis

- **High Dominance of Concise Shape**: Captureless single-expression lambdas represent nearly **1 in 4 lambdas** (22.61%) inside the LLVM codebase.
- **Predominant Captureless Form**: Out of all lambdas that do not require any captures (and thus could utilize a captureless concise form), **62.77%** consist of a single expression.
- **Syntactic Overhead Reduction**: Introducing the proposed concise syntax `(params) => expr` would eliminate up to 18 characters of syntactic scaffolding for **9,799 instances** in LLVM alone, significantly improving code readability and reducing semantic clutter.

# Implementation experience

A minimal working prototype reference implementation in Clang has been developed
and is available [here](https://github.com/S-Spektrum-M/llvm-project). Implementation experience will be shared in a
future revision.

# Wording sketch

The following is indicative, not normative; full wording will follow
EWG direction in R1.

In [expr.prim], add a new subsection [expr.prim.lambda.concise]:

> A *concise-lambda-expression* `(` *L* `)` `=>` *E* is equivalent to
> the *lambda-expression*
>
> &nbsp;&nbsp;`[]` `(` *L′* `)` `{ return` *E* `; }`
>
> where *L′* is obtained from *L* by replacing each
> *concise-lambda-parameter* that consists of an *identifier* `x` with
> the *parameter-declaration* `auto&& x`, and leaving each
> *parameter-declaration* unchanged.

In [lex.operators], add `=>` to the list of possible values of *operator-or-punctuator*.

In [gram.expr], extend *primary-expression* with the new alternative.

# Acknowledgments

Thanks to the prior authors of abbreviated-lambda proposals, whose
designs informed the boundary conditions of this one. Thanks also to
the maintainers of the WG21 paper template for making R0 drafts
substantially less painful than they would otherwise be.
