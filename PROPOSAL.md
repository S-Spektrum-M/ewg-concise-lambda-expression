---
title: "Concise Lambda Expressions"
document: PXXXXR0
date: today
audience:
  - EWGI
  - EWG
author:
  - name: Siddharth Mohanty
    email: <neosiddharth@gmail.com>
toc: true
---

# Revision History {#revision-history}

N/A.

# Abstract {#abstract}

This paper proposes a concise lambda expression syntax of the form
`(params) => expr`{.cpp}, which lowers to a captureless generic lambda whose
parameters default to forwarding references and whose return type is deduced
via standard `auto`{.cpp} rules. The syntax is purely additive. It introduces
the token (`=>`{.cpp}) into *primary-expression* along with a new lambda
production, leaving the existing lambda grammar untouched.

An empirical analysis across five major codebases (Abesil, Chromium, Folly, LLVM,
and QtBase) finds that single-expression lambdas account for
52.67% of all lambdas, and of the lambdas that need no capture, 60.27% are
single-expression. This proposal deliberately scopes to the captureless
single-expression form (23.45% of all lambdas). In range pipelines, algorithm
calls, and projection arguments, the syntactic overhead of the current form is
disproportionate to its semantic weight.

# Motivation {#motivation}

The C++ lambda has matured into the de facto unit of local function
abstraction, but the syntactic weight of the construct has not changed
since C++11. A simple squaring callable is:

```cpp
[](auto &&x) { return x * x; };
```

The same callable in JavaScript, C#, Scala, and several other
contemporary languages is `(x) => x * x` or `x => x * x`.

The C++ form contains 18 characters of syntactic scaffolding including:

- Capture brackets (for a captureless pure function).
- Parameter type (in a declaration where the type would be automatically inferred anyway).
- The `return`{.cpp} keyword and surrounding braces (in a single expression function).

For range pipelines this overhead is amplified, since lambdas tend to
appear several times per pipeline:

::: cmptable

### C++23
```cpp
auto result = v
    | std::views::filter([](auto &&x) {
        return x > 0;
      })
    | std::views::transform([](auto &&x) {
        return x * x;
      })
    | std::views::take_while([](auto &&x) {
        return x < 100;
      });
```

### This Paper
```cpp
auto result = v
    | std::views::filter((x) => x > 0)
    | std::views::transform((x) => x * x)
    | std::views::take_while((x) => x < 100);
```

:::

The existing form obscures the pipeline actions behind lambda syntax. By
dropping the lambda syntax, the pipeline achieves a higher signal-noise ratio.

This proposal provides a first-class syntax for single-expression captureless
callables.

Cases that require capture, multiple statements, explicit return types, template
parameter lists, or `mutable`{.cpp}/`consteval`{.cpp}/`static`{.cpp} operators continue to be
expressible via the existing *lambda-expression* syntax.

# Proposal {#proposal}

## Syntax {#syntax}

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

The token `=>`{.cpp} is also introduced into primary-expression by this proposal.
The same token serves as the match-arm separator in the pattern-matching
proposal [@P2688R5]; [](#pattern-matching) explains why the two uses do not conflict.

## Semantics {#semantics}

A `concise-lambda-expression` of the form `(p_1, ..., p_N) => E` is
equivalent to the `lambda-expression`:

```cpp
[] ($P_1$, ..., $P_N$) { return $E$; }
```

where each `P_i` is determined from `p_i` as follows:

- If `p_i` is an identifier `x` with no accompanying `decl-specifier-seq`, then `P_i` is `auto &&x`.
- If `p_i` is a `parameter-declaration`, `P_i` is `p_i` unchanged.

If a `concise-lambda-parameter` can be interpreted as both an identifier and a `parameter-declaration` (such as when it consists of a single type-name), it is interpreted as an identifier.

The lambda has no `lambda-capture` and no `lambda-specifier-seq`. The
resulting closure type is implicitly `constexpr`-callable wherever a
captureless lambda of the corresponding equivalent form would be.

## Examples {#examples}

```cpp
auto square    = (x) => x * x;              // [] (auto &&x) { return x * x;}
auto add       = (x, y) => x + y;           // [] (auto &&x, auto &&y) {return x + y;};
auto identity  = (x) => x;                  // [] (auto &&x) -> auto {return x;}
                                            // returns a copy
auto greet     = () => std::puts("hi");     // returns int (the result of puts)

// Mixing inferred and explicit parameter forms
auto clamp_pos = (int x) => std::max(0, x);
auto container_access = (db, size_t y) => db[y];

// Concepts, void, and throw
auto add_one = (std::integral auto x) => x + 1;
auto log_err = (e) => std::println(std::cerr, "{}", e);
auto error = (x) => throw std::runtime_error("error");
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

// Parameter Packs
auto print_hello = (auto... xs) => std::println("Hello, {} from {}!", xs...);

```

The body of a concise-lambda-expression is an *assignment-expression*, so `=>`
binds more tightly than the comma operator. Consequently `(x) => a, b`{.cpp}
parses as `((x) => a), b`{.cpp}, and in an argument list `f((x) => x, 0)`{.cpp}
passes `0`{.cpp} as a second argument to `f` rather than extending the body —
usually the intended reading. A body that is itself a comma-expression must
therefore be parenthesized, which also enables sequencing several side effects
in a single concise lambda:

```cpp
auto log_and_return = (x) => (std::cout << "got " << x, x + 1);
```

## Restrictions {#restrictions}

A *concise-lambda-expression* shall not:

- introduce a *lambda-capture*
- declare a return type explicitly
- declare a template parameter list
- apply `mutable`{.cpp}, `static`{.cpp}, `consteval`{.cpp}, `constexpr`{.cpp},
or other *lambda-specifier*s
- use a *requires-clause*
- declare default arguments
- or contain a *compound-statement* body.

Code requiring any of these continues to use the existing
*lambda-expression* form.

# Discussion {#discussion}

## Why no Captures {#why-no-captures}

The single most common source of subtle bugs in lambda-heavy code is
implicit capture of references that outlive their referent.

Mandating an empty capture list at the syntactic level converts an entire
class of dangling-reference bugs into a syntactic refusal. If the body of the
concise lambda would have required a capture, the compiler diagnoses an
unrelated lookup failure for the named entity and the user falls back to
the explicit form.

It is acknowledged that this introduces a "syntax cliff."
Empirical data (see [](#empirical-analysis)) shows that single-expression lambdas that *do*
capture state are actually slightly more common (29.22% of all lambdas)
than those that do not (23.45%). However, extending the syntax to support explicit
captures (e.g., `[capture_list] (params) => expr`{.cpp}) would reintroduce the capture group syntax that this
proposal aims to eliminate, eroding the brevity of the construct.

Concise lambdas may, of course, reference entities with linkage —
globals, namespace-scope functions, and static members. What is *not*
available is access to the non-static members of an enclosing class,
because that would require capturing `this`{.cpp}. For lambdas inside member
functions that need `this`{.cpp}, the existing lambda form remains.

## `auto` Return Type {#auto-return-type}

The concise lambda lowers to an implicit `auto`{.cpp} return type, exactly as
standard lambdas do. This strips references and cv-qualifiers, so the lambda
returns by value.

We considered two reference-preserving alternatives and rejected both.
`decltype((E))`{.cpp} (as used by [@P0573R2]) parenthesizes the body,
so any lvalue body yields an lvalue-reference return type. Given a projection
`(e) => e.address.city`{.cpp} over a view that yields prvalues, the `auto &&`{.cpp}
parameter `e` binds to a temporary, `e.address.city`{.cpp} is an lvalue subobject
of it, and the deduced return type `std::string &`{.cpp} is a reference into
that temporary, therefore, it dangles the moment the temporary is destroyed.

`decltype(auto)`{.cpp} is harder to reason about rather than safer, because its
result depends on the syntactic form of the body. Consider the following
examples:

1. `return e.address.city;`{.cpp} deduces `std::string`{.cpp} by value.
2. `return (e.address.city);`{.cpp} deduces `std::string &`{.cpp} because of the
parentheses.
3. `return x;`{.cpp} deduces the parameter's declared type as a reference into
the `auto &&`{.cpp} parameter

This form-sensitivity is precisely the property that drew objections to
[@P0573R2].

By defaulting to `auto`{.cpp}, the concise lambda always returns a value. This is the
right default for the overwhelming majority of uses — predicates, arithmetic
transforms, and the projections and comparators that feed standard algorithms.
Users who explicitly need to return a reference (e.g., to build a custom view)
fall back to the explicit lambda syntax `[](auto &&x) -> auto& { return x.name; }`{.cpp}.

This creates a deliberate asymmetry with the parameter default
(see [](#inferred-parameters)): `auto &&`{.cpp} avoids a copy at the parameter boundary,
while `auto`{.cpp} introduces one at the result boundary. This incurs a performance
cost when the body names an existing subobject. For example, using
`(e) => e.address.city`{.cpp} in `std::ranges::sort`{.cpp} materializes a new
`std::string`{.cpp} copy on every comparison, whereas
`[](auto &&e) -> auto& { return e.address.city; }`{.cpp} avoids the copy entirely.

We accept this copying overhead deliberately. The dangling reference hazard is
a far worse failure mode than a suboptimal copy, and performance-critical users
can explicitly use the *lambda-expression* production when safe.

## Why `auto &&` for Inferred Parameters {#inferred-parameters}

The default parameter type is `auto &&`{.cpp}. This acts as a forwarding
reference, allowing the lambda to bind to prvalues, lvalues, const, and
non-const arguments without ever incurring an implicit copy at the parameter
boundary.

There are three plausible candidates for the default:

1. `auto`{.cpp} silently copies. A concise lambda of the form
`(p) => p.size()`{.cpp} applied to a `std::string` would copy the string per
invocation.
2. `const auto &`{.cpp} binds safely, but rejects mutable algorithms. The
expression `(x) => ++x`{.cpp} becomes ill-formed because of the implicit
cv-qualifier.
3. `auto &&`{.cpp} is the only form that universally binds to the caller's
argument without copying and without imposing unrequested constness.

Crucially, `auto &&`{.cpp} parameter is evaluated as an lvalue within the body
`E` (as all named variables are in C++). We do not attempt implicit perfect
forwarding (e.g., wrapping usages in `std::forward`). If a user needs to
perfectly forward the value category of the argument to an overloaded function
inside the body, they should use the explicit lambda syntax. For the vast
majority of concise lambda use cases—member access, operators, and by-value
transformations—the lvalue evaluation of the `auto &&`{.cpp} parameter is exactly
what is required. The same holds for parameter packs: in
`(auto&&... xs) => f(xs...)`{.cpp} each `xs`{.cpp} is an lvalue, so the call
does not forward; a forwarding wrapper requires the explicit lambda form.

When a user wants something else (e.g. `int`, `const std::string &`,
`auto` by value) they can opt into the full *parameter-declaration*.

A user who wants by-value semantics writes `(auto x) => ...`{.cpp} whereas a
user who wants const-lvalue semantics writes `(const auto &x) => ...`{.cpp}.
Both are a few characters longer than the bare-identifier form and immediately
self-documenting at the point of use.

## SFINAE Hostility {#sfinae}

Like any generic lambda with a deduced return type, a concise lambda is
SFINAE-hostile. Its `operator()`{.cpp} is an unconstrained template whose
signature is always valid; the return type is determined only by instantiating
the body. Because that instantiation is outside the immediate context of
template argument deduction, a body that is ill-formed for some argument type
produces a hard error rather than a removable candidate. A concise lambda
therefore cannot be used to drive constraint checks or overload resolution —
even *querying* it is ill-formed. For `auto sizer = (x) => x.size();`{.cpp},
evaluating `std::invocable<decltype(sizer), int>`{.cpp} instantiates
`x.size()`{.cpp} on `int`{.cpp} and emits a hard error, poisoning the
translation unit, even though the trait would otherwise report `false`{.cpp}.
This is not specific to the concise form: the explicit
`[](auto&& x) { return x.size(); }`{.cpp} produces an identical diagnostic
(verified against the reference implementation). The lighter syntax, however,
invites generic lambdas into precisely the constrained contexts — predicates
for constrained algorithms, customization points — where the limitation bites.

A SFINAE-friendly callable must spell a trailing return type,

`auto sizer_sfinae = [](auto&& x) -> decltype(x.size()) { return x.size(); }`{.cpp},

which moves the failure into the immediate context; the same check then
yields a clean `false`{.cpp} with no hard error. We deliberately do not give
the concise form an implicit `-> decltype(E)`{.cpp}, as that reintroduces the
form-sensitivity and dangling hazards discussed in [](#auto-return-type).

## Why Parentheses Are Required Around the Parameter List {#parentheses}

The bare-identifier form, `x => x * x`{.cpp}, is admitted by JavaScript and C#.
We considered it and rejected it. Requiring parentheses gives the concise lambda
a single, uniform shape across all arities — `() =>`{.cpp}, `(x) =>`{.cpp},
`(x, y) =>`{.cpp} — rather than a special paren-less spelling that applies only
to the one-untyped-parameter case. It also gives the parser one anchor: the
opening `(` is the trigger for the tentative parse described in
[](#parsing-considerations), whereas a bare identifier would make every
*id-expression* in expression context a potential lambda head. The cost is two
characters in the single-parameter case, which we judge an acceptable price for
a uniform rule and a single syntactic entry point.

## Static Call Operator {#static-call-operator}

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

This is, however, a defensible alternative design and is called out explicitly
for consideration.

## `noexcept` Semantics {#noexcept-semantics}

Because concise lambdas omit the *lambda-specifier-seq*, they cannot be explicitly
marked `noexcept`. A natural alternative is implicit deduction: lowering to
`noexcept(noexcept(E))`{.cpp}.

Despite this appeal, the current design does not deduce `noexcept`.
The primary motivation is refactoring stability: when a user converts a concise
lambda into an explicit lambda (e.g., to add a capture or a second statement),
the closure type's exception specification should not silently change. An
implicitly-deduced `noexcept` in the concise form would be quietly
lost in the explicit form, potentially weakening `noexcept`
guarantees that callers had come to rely on without any diagnostic.

This mirrors existing lambda behaviour as standard lambdas do not implicitly deduce `noexcept` either.
This decision keeps the two forms interchangeable in this respect.

Users requiring a `noexcept` callable must use the explicit lambda form and spell the specifier.

## Interaction With `constexpr` {#constexpr}

Concise lambdas are implicitly `constexpr` under exactly the same
conditions as captureless explicit lambdas — i.e., always, modulo the
constexpr-eligibility of `E`. No additional rule is required; this
follows from the rewriting in [](#semantics).

## Attributes {#attributes}

It is not yet settled whether attributes should be permitted on concise lambda
parameters (e.g., `([[maybe_unused]] x) => x`{.cpp}) or on the generated call operator.
Because this syntax omits the `lambda-specifier-seq`, standard placement for
operator attributes (like `[[nodiscard]]`) is unavailable. Attributes applied
to the *primary-expression* containing the lambda do not appertain to the
generated `operator()`. We intend to seek EWG feedback on whether to extend
the grammar to explicitly support attributes or to leave them unsupported for
this minimal syntax.

# Parsing Considerations {#parsing-considerations}

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

While finding the matching close parentheses requires scanning ahead an
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

## Interaction with Pattern Matching {#pattern-matching}

[@P2688R5] introduces `=>` as the separator between a *pattern* and its
result expression inside a `match` expression. The two uses of `=>` occur
in disjoint grammatical contexts: in [@P2688R5] the `=>` follows a *pattern*,
whereas a *concise-lambda-expression*'s `=>` follows a parenthesized
*concise-lambda-parameter-list* in *primary-expression* position. A concise
lambda composes with `match` in both directions — a concise lambda may be
the result expression of an arm, and a `match` expression may be the body
`E` of a concise lambda — without ambiguity, because the arm's `=>` is
reached only after a pattern is parsed and the body's `=>` only after a
parenthesized list.

# Prior Art {#prior-art}

Abbreviated-lambda proposals have appeared periodically in the WG21
record. Most directly, [@P0573R2] ("Abbreviated Lambdas for Fun and
Profit", Revzin and Kamiński) proposed a `=>` form in which
`[](auto &&x) => E` was defined to mean

```cpp
[](auto &&x) -> decltype(($E$)) noexcept(noexcept($E$)) { return $E$; }
```

retaining the `[]` introducer and the full parameter list while
abbreviating only the body. It was presented to EWG in Albuquerque in
November 2017 and rejected, 6–17. The same session, however, polled
18–2 in favour of considering a *future* shorter-lambda proposal that
presents new technical information.

This paper is offered in that spirit, and is designed to address the
substance of the original objections rather than merely respell the
syntax:

  1. **New empirical motivation.** [](#empirical-analysis)
     quantifies, across five major codebases, how prevalent the targeted
     form actually is — data that was not before EWG in 2017.
  2. **A deliberately smaller semantic core.** The contentious heart of
     [@P0573R2] was its return and exception semantics: deducing the
     return type via `decltype((E))` and propagating
     `noexcept(noexcept(E))` — the "spell it three times" behaviour that
     drew the bulk of the discussion. This proposal abandons both,
     lowering to a plain `auto` return type with no `noexcept` deduction
     (see [](#auto-return-type) and [](#noexcept-semantics)). It therefore
     adds no second return-type-deduction mode to the language and trades
     completeness for a smaller, more predictable rule.
  3. **No `[]` introducer.** The `[capture-list]` syntax is the most
     visually distinctive — and most syntactically expensive — part of
     the current lambda. Removing it entirely (rather than allowing
     `[]` to be elided) makes the new form clearly distinct from the
     existing one rather than a shorter spelling of it.
  4. **No captures, by design.** This is a feature, not a limitation;
     see [](#why-no-captures).
  5. **Parameter types are optional.** The user opts into specificity
     rather than opting out of verbosity.

The result is a construct that is closer in spirit to mathematical
function notation and to the lambda forms of contemporary high-level
languages, while remaining a strict subset of what the existing C++
lambda can express.

# Impact on existing code {#impact-on-existing-code}

None. The proposed feature is purely additive. The `=>` token does not
appear in any well-formed C++ program under the current standard. The only other
prospective use case is the match-arm separator of [@P2688R5], addressed in
[](#pattern-matching). The new grammar production is reachable only via the new
token. No existing lambda syntax, semantics, or closure-type properties are
changed.

One exceedingly minor edge case involves the preprocessor: token pasting
`PASTE(=, >)` will now form a valid `=>` token under this proposal, whereas it yields an invalid token in C++23.

ABI is unaffected: a concise lambda lowers to an explicit lambda whose ABI is already specified.

# Empirical Analysis: Large-Scale C++ Codebases {#empirical-analysis}

To evaluate the assertion that captureless, single-expression lambdas are
dominant in modern C++, we conducted an empirical analysis
across several major open-source C++ codebases.

These repositories represent a diverse mix of large-scale, performance-critical
C++ projects containing extensive modern C++ usage (e.g., standard library
algorithms, range adapters, and projections).

A custom lexical parser scanned over **196,000 C++ source and header files** across these codebases to classify all C++ lambda expressions based on their captures and body complexity.

Because this classifier is lexical rather than a full semantic parse, the
figures below should be read as close approximations rather than exact
counts: macro-generated lambdas, lambdas with deeply nested or multi-line
bodies, and code behind preprocessor conditionals may be mis-binned. The
analysis tool is available [here](https://github.com/S-Spektrum-M/ewg-concise-lambda-expression/blob/main/scratch/count_lambdas.py)
so the figures can be independently reproduced; a future revision intends
to corroborate them with an AST-based pass.

## Findings {#findings}

The analysis discovered a grand total of **117,548 lambda expressions**. The aggregated results across all five codebases are categorized as follows:

| Metric | Count | Percentage |
| :--- | :--- | :--- |
| **Total Lambdas Found** | **117,548** | **100.00%** |
| **Captureless Lambdas (`[]`)** | **45,737** | **38.91%** |
| **Captureless Single-Expression Lambdas** | **27,564** | **23.45%** of all lambdas |
| **Captured Single-Expression Lambdas** | **34,348** | **29.22%** of all lambdas |

### Breakdown by Repository

| Repository | Files Scanned | Total Lambdas | Captureless | Captureless Single-Expr | Captured Single-Expr |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Abseil** | 867 | 1,059 | 607 (57.3%) | 334 (31.5%) | 204 (19.3%) |
| **Chromium** | 129,516 | 59,145 | 24,853 (42.0%) | 14,611 (24.7%) | 16,603 (28.1%) |
| **Folly** | 2,309 | 7,409 | 2,518 (34.0%) | 1,563 (21.1%) | 2,173 (29.3%) |
| **LLVM** | 55,413 | 43,418 | 15,627 (36.0%) | 9,810 (22.6%) | 13,055 (30.1%) |
| **QtBase** | 8,666 | 6,517 | 2,132 (32.7%) | 1,246 (19.1%) | 2,313 (35.5%) |

## Analysis {#analysis}

- **High Dominance of Single-Expression Shape**: Single-expression lambdas (both captured and captureless) represent **52.67%** of all lambdas across these codebases.
- **Predominant Captureless Form**: Out of all lambdas that do not require any captures, **60.27%** consist of a single expression, making them prime candidates for the concise syntax.
- **The Capture Gap**: While captureless single-expression lambdas are highly prevalent (23.45%), captured single-expression lambdas are actually more common (29.22%). This highlights the "syntax cliff" discussed in [](#why-no-captures).
- **Syntactic Overhead Reduction**: Introducing the proposed concise syntax `(params) => expr` would eliminate up to 18 characters of syntactic scaffolding for over **27,500 instances** in these repositories alone, significantly improving code readability and reducing semantic clutter.

# Implementation experience {#implementation-experience}

A minimal working prototype reference implementation in Clang has been developed
and is available [here](https://github.com/S-Spektrum-M/llvm-project). Implementation experience will be shared in a
future revision.

# Wording sketch {#wording-sketch}

The following is not final; full wording will follow EWG direction in R1.

In [expr.prim]{.sref}, add a new subclause [expr.prim.lambda.concise] ("Concise lambda expressions"):

::: add
### [expr.prim.lambda.concise] Concise lambda expressions {.unnumbered}

| _concise-lambda-expression:_
|     `(` _concise-lambda-parameter-list~opt~_ `)` `=>` _assignment-expression_
|
| _concise-lambda-parameter-list:_
|     _concise-lambda-parameter_
|     _concise-lambda-parameter-list_ `,` _concise-lambda-parameter_
|
| _concise-lambda-parameter:_
|     _identifier_
|     _parameter-declaration_

[1]{.pnum} A *concise-lambda-expression* `(` *L* `)` `=>` *E* is equivalent to
the *lambda-expression*
`[]` `(` *L′* `)` `{ return` *E* `; }`
where *L′* is obtained from *L* by replacing each
*concise-lambda-parameter* that consists of an *identifier* `x` with
the *parameter-declaration* `auto &&x`, and leaving each
*parameter-declaration* unchanged.
If a *concise-lambda-parameter* can be interpreted as both an *identifier* and a *parameter-declaration*, it is interpreted as an *identifier*.

[2]{.pnum} A *concise-lambda-parameter* that is a *parameter-declaration* shall not contain a default argument.
:::

In [lex.operators]{.sref}, add `=>` to the list of possible values of *operator-or-punctuator*:

::: add
| _operator-or-punctuator:_ one of
|     ...
|     `=>`
:::

In [gram.expr]{.sref}, extend *primary-expression* with the new alternative:

::: add
| _primary-expression:_
|     ...
|     _concise-lambda-expression_
:::

In [gram.expr]{.sref}, add the new productions for *concise-lambda-expression*:

::: add
| _concise-lambda-expression:_
|     `(` _concise-lambda-parameter-list~opt~_ `)` `=>` _assignment-expression_
|
| _concise-lambda-parameter-list:_
|     _concise-lambda-parameter_
|     _concise-lambda-parameter-list_ `,` _concise-lambda-parameter_
|
| _concise-lambda-parameter:_
|     _identifier_
|     _parameter-declaration_
:::

# Acknowledgments {#acknowledgments}

Thanks to the prior authors of abbreviated-lambda proposals, whose
designs informed the boundary conditions of this one. Thanks also to
the maintainers of the WG21 paper template for making R0 drafts
substantially less painful than they would otherwise be.
