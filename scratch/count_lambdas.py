#!/usr/bin/env python3
import os
import re
import sys
import argparse
import time
import subprocess
from concurrent.futures import ProcessPoolExecutor

# Tokenizer pattern
TOKEN_RE = re.compile(r'''
    (?P<IDENT>[a-zA-Z_][a-zA-Z0-9_]*)
    |(?P<ARROW>->)
    |(?P<DBL_COLON>::)
    |(?P<DBL_LBRACK>\[\[)
    |(?P<DBL_RBRACK>\]\])
    |(?P<LBRACK>\[)
    |(?P<RBRACK>\])
    |(?P<LBRACE>\{)
    |(?P<RBRACE>\})
    |(?P<LPAR>\()
    |(?P<RPAR>\))
    |(?P<SEMI>;)
    |(?P<COMMA>,)
    |(?P<EQ>=)
    |(?P<SYM>[+\-*/%&|^~<>!?.:])
    |(?P<NUM>[0-9]+(?:\.[0-9]+)?)
    |(?P<WS>\s+)
''', re.VERBOSE)

def strip_comments_and_strings(code):
    result = []
    i = 0
    n = len(code)
    while i < n:
        # Check raw string first
        if i + 2 < n and code[i:i+2] == 'R"':
            delim_start = i + 2
            delim_end = code.find('(', delim_start)
            if delim_end != -1:
                delim = code[delim_start:delim_end]
                end_marker = ')' + delim + '"'
                end_pos = code.find(end_marker, delim_end)
                if end_pos != -1:
                    result.append('""')
                    i = end_pos + len(end_marker)
                    continue

        # Check normal string
        if code[i] == '"':
            j = i + 1
            while j < n:
                if code[j] == '\\':
                    j += 2
                elif code[j] == '"':
                    break
                else:
                    j += 1
            result.append('""')
            i = j + 1
            continue

        # Check char literal
        if code[i] == "'":
            j = i + 1
            while j < n:
                if code[j] == '\\':
                    j += 2
                elif code[j] == "'":
                    break
                else:
                    j += 1
            result.append("''")
            i = j + 1
            continue

        # Check single-line comment
        if i + 1 < n and code[i:i+2] == '//':
            j = code.find('\n', i + 2)
            if j == -1:
                j = n
            result.append('\n')
            i = j
            continue

        # Check multi-line comment
        if i + 1 < n and code[i:i+2] == '/*':
            j = code.find('*/', i + 2)
            if j == -1:
                j = n
            else:
                j += 2
            result.append(' ')
            i = j
            continue

        result.append(code[i])
        i += 1

    return "".join(result)

def tokenize(code):
    tokens = []
    for match in TOKEN_RE.finditer(code):
        kind = match.lastgroup
        value = match.group(kind)
        if kind != 'WS':
            tokens.append((kind, value, match.start()))
    return tokens

def find_lambdas(tokens):
    n = len(tokens)

    # Helper to build nesting maps
    def build_nesting_maps():
        bracket_map = {}
        paren_map = {}
        brace_map = {}

        bracket_stack = []
        paren_stack = []
        brace_stack = []

        for idx, (kind, val, pos) in enumerate(tokens):
            if kind == 'LBRACK':
                bracket_stack.append(idx)
            elif kind == 'RBRACK':
                if bracket_stack:
                    start = bracket_stack.pop()
                    bracket_map[start] = idx
            elif kind == 'LPAR':
                paren_stack.append(idx)
            elif kind == 'RPAR':
                if paren_stack:
                    start = paren_stack.pop()
                    paren_map[start] = idx
            elif kind == 'LBRACE':
                brace_stack.append(idx)
            elif kind == 'RBRACE':
                if brace_stack:
                    start = brace_stack.pop()
                    brace_map[start] = idx

        return bracket_map, paren_map, brace_map

    bracket_map, paren_map, brace_map = build_nesting_maps()

    KEYWORDS = {
        'return', 'throw', 'co_return', 'co_yield', 'delete', 'new', 'sizeof',
        'alignof', 'decltype', 'co_await', 'case', 'goto', 'const_cast',
        'static_cast', 'dynamic_cast', 'reinterpret_cast', 'else', 'do',
        'typedef', 'using', 'friend', 'explicit', 'virtual', 'inline'
    }

    CONTROL_FLOW_KEYWORDS = {
        'if', 'for', 'while', 'do', 'switch', 'try', 'catch', 'break',
        'continue', 'goto', 'struct', 'class', 'union', 'using', 'typedef',
        'decltype'
    }

    lambdas = []

    i = 0
    while i < n:
        kind, val, pos = tokens[i]

        if kind == 'LBRACK':
            # Preceded-by checks to filter out array subscript/operator[]
            is_valid_introducer = True
            if i > 0:
                prev_kind, prev_val, prev_pos = tokens[i-1]
                if prev_kind == 'IDENT':
                    if prev_val == 'operator':
                        is_valid_introducer = False
                    elif prev_val not in KEYWORDS:
                        is_valid_introducer = False
                elif prev_kind in ('RPAR', 'RBRACK', 'DBL_RBRACK'):
                    is_valid_introducer = False
                elif prev_kind == 'SYM' and prev_val in ('.', '->'):
                    is_valid_introducer = False

            if is_valid_introducer and i in bracket_map:
                rbracket_idx = bracket_map[i]

                # Now scan forward from rbracket_idx + 1 to find '{' (body start)
                k = rbracket_idx + 1
                body_start_idx = None
                in_trailing_return = False
                in_requires_clause = False

                ALLOWED_SPECIFIERS = {
                    'mutable', 'constexpr', 'consteval', 'static', 'noexcept',
                    'const', 'volatile', 'decltype'
                }

                while k < n:
                    k_kind, k_val, k_pos = tokens[k]
                    if k_kind == 'SYM' and k_val == '<':
                        # Template parameter list, skip to matching '>'
                        depth = 1
                        scan_k = k + 1
                        while scan_k < n and depth > 0:
                            sk_kind, sk_val, sk_pos = tokens[scan_k]
                            if sk_kind == 'SYM' and sk_val == '<':
                                depth += 1
                            elif sk_kind == 'SYM' and sk_val == '>':
                                depth -= 1
                            elif sk_kind in ('SEMI', 'LBRACE'):
                                break
                            scan_k += 1
                        if depth == 0:
                            k = scan_k
                            continue
                        else:
                            break
                    elif k_kind == 'LPAR':
                        # Parameter list, skip to matching RPAR
                        if k in paren_map:
                            k = paren_map[k] + 1
                            continue
                        else:
                            break
                    elif k_kind == 'LBRACE':
                        # Body start!
                        body_start_idx = k
                        break
                    elif k_kind == 'ARROW':  # ->
                        in_trailing_return = True
                        k += 1
                    elif k_kind == 'IDENT' and k_val == 'requires':
                        in_requires_clause = True
                        k += 1
                    elif k_kind in ('SEMI', 'EQ', 'COMMA', 'RBRACE', 'RPAR', 'RBRACK'):
                        # Semicolon, equals, comma, or unmatched closing symbols are not allowed
                        break
                    elif in_trailing_return:
                        # Inside trailing return, allow types, qualifiers, operators
                        if k_kind in ('IDENT', 'DBL_COLON', 'SYM', 'NUM'):
                            k += 1
                        else:
                            break
                    elif in_requires_clause:
                        # Inside requires clause, allow anything except brace/semi
                        if k_kind not in ('LBRACE', 'SEMI'):
                            k += 1
                        else:
                            break
                    elif k_kind == 'IDENT' and k_val in ALLOWED_SPECIFIERS:
                        k += 1
                    else:
                        break

                if body_start_idx is not None and body_start_idx in brace_map:
                    body_end_idx = brace_map[body_start_idx]

                    # Capture list
                    capture_list = tokens[i+1 : rbracket_idx]
                    # Body list
                    body = tokens[body_start_idx+1 : body_end_idx]

                    # 1. Captureless check: capture list must be empty
                    is_captureless = (len(capture_list) == 0)

                    # 2. Single-expression check
                    # Count top-level semicolons in the body
                    top_level_semi_count = 0
                    has_control_flow = False

                    b_paren_depth = 0
                    b_bracket_depth = 0
                    b_brace_depth = 0

                    for bt_idx, (bt_kind, bt_val, bt_pos) in enumerate(body):
                        if bt_kind == 'LBRACE':
                            b_brace_depth += 1
                        elif bt_kind == 'RBRACE':
                            b_brace_depth -= 1
                        elif bt_kind == 'LPAR':
                            b_paren_depth += 1
                        elif bt_kind == 'RPAR':
                            b_paren_depth -= 1
                        elif bt_kind == 'LBRACK':
                            b_bracket_depth += 1
                        elif bt_kind == 'RBRACK':
                            b_bracket_depth -= 1
                        elif bt_kind == 'SEMI':
                            if b_brace_depth == 0 and b_paren_depth == 0 and b_bracket_depth == 0:
                                top_level_semi_count += 1
                        elif bt_kind == 'IDENT':
                            if b_brace_depth == 0 and bt_val in CONTROL_FLOW_KEYWORDS:
                                has_control_flow = True

                    is_single_expr = (top_level_semi_count == 1) and not has_control_flow

                    lambdas.append({
                        'captureless': is_captureless,
                        'single_expression': is_single_expr,
                        'capture_span': "".join(t[1] for t in capture_list),
                        'body_tokens_count': len(body),
                        'start_pos': pos
                    })

        i += 1

    return lambdas

def analyze_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()
    except Exception as e:
        return {'error': str(e), 'filepath': filepath}

    clean_code = strip_comments_and_strings(code)
    tokens = tokenize(clean_code)
    lambdas = find_lambdas(tokens)

    total = len(lambdas)
    captureless = sum(1 for l in lambdas if l['captureless'])
    captureless_single_expr = sum(1 for l in lambdas if l['captureless'] and l['single_expression'])

    return {
        'filepath': filepath,
        'total': total,
        'captureless': captureless,
        'captureless_single_expr': captureless_single_expr,
        'lambdas': lambdas
    }

def run_self_tests():
    print("Running self-tests...")
    test_cases = [
        # 1. Captureless single-expression
        ("[](auto x) { return x * x; };", 1, 1, 1),
        # 2. Captureless multi-expression
        ("[](int x) { int y = x; return y * y; };", 1, 1, 0),
        # 3. Captured single-expression
        ("[factor](int x) { return x * factor; };", 1, 0, 0),
        # 4. Double bracket attributes (not a lambda)
        ("[[nodiscard]] int main() { return 0; }", 0, 0, 0),
        # 5. Array subscript (not a lambda)
        ("arr[idx] = 10;", 0, 0, 0),
        # 6. Structured binding (not a lambda)
        ("auto [x, y] = get_pair();", 0, 0, 0),
        # 7. Nested lambdas (outer captureless single-expr returning captureless single-expr)
        ("[]() { return []() { return 42; }; };", 2, 2, 2),
        # 8. Operator [] (not a lambda)
        ("T& operator[](size_t index) { return data[index]; }", 0, 0, 0),
        # 9. Complex lambda with trailing return and template list
        ("[] <typename T> (T x) -> auto { return x + 1; };", 1, 1, 1),
        # 10. String literal and comments containing lambda-like text
        ('// []() { return 1; };\n/* [](int x) { return x; } */\nstd::string s = "[]() { return 42; }";', 0, 0, 0),
        # 11. Lambda with void-returning single expression
        ("[]() { do_something(); };", 1, 1, 1),
        # 12. Lambda with multiple statements inside nested structures but top-level single statement
        ("[]() { std::for_each(v.begin(), v.end(), [](int x) { puts(\"ok\"); }); };", 2, 2, 2),
    ]

    passed = 0
    for idx, (code, exp_total, exp_cap, exp_cap_single) in enumerate(test_cases):
        clean = strip_comments_and_strings(code)
        tokens = tokenize(clean)
        lambdas = find_lambdas(tokens)

        total = len(lambdas)
        captureless = sum(1 for l in lambdas if l['captureless'])
        captureless_single_expr = sum(1 for l in lambdas if l['captureless'] and l['single_expression'])

        ok = (total == exp_total) and (captureless == exp_cap) and (captureless_single_expr == exp_cap_single)
        if ok:
            passed += 1
            print(f"Test {idx + 1}: PASSED")
        else:
            print(f"Test {idx + 1}: FAILED!")
            print(f"  Code: {code}")
            print(f"  Expected: Total={exp_total}, Captureless={exp_cap}, CapSingle={exp_cap_single}")
            print(f"  Got:      Total={total}, Captureless={captureless}, CapSingle={captureless_single_expr}")
            print(f"  Lambdas found: {lambdas}")

    print(f"\nSelf-tests complete: {passed}/{len(test_cases)} passed.")
    if passed != len(test_cases):
        sys.exit(1)

REPO_URLS = {
    "llvm-project": "https://github.com/llvm/llvm-project.git",
    "abseil-cpp": "https://github.com/abseil/abseil-cpp.git",
    "chromium": "https://github.com/chromium/chromium.git",
    "folly": "https://github.com/facebook/folly.git",
    "qtbase": "https://github.com/qt/qtbase.git",
}

def analyze_directory(repo_dir, workers, verbose):
    print(f"\nScanning directory: {repo_dir}")
    print("Collecting C++ files...")

    extensions = {'.cpp', '.h', '.hpp', '.cc', '.cxx', '.hh', '.hxx'}
    files_to_scan = []
    for root, _, files in os.walk(repo_dir):
        # Skip .git directories
        if '.git' in root.split(os.sep):
            continue
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in extensions:
                files_to_scan.append(os.path.join(root, file))

    num_files = len(files_to_scan)
    print(f"Found {num_files} C++ source/header files in {repo_dir}.")

    if num_files == 0:
        print("No files found to scan.")
        return None

    print(f"Analyzing files using up to {workers or 'default'} parallel processes...")
    start_time = time.time()

    total_lambdas = 0
    total_captureless = 0
    total_captureless_single = 0
    scanned_files_count = 0
    error_files = []

    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = executor.map(analyze_file, files_to_scan)

        for result in results:
            if 'error' in result:
                error_files.append(result)
                continue

            scanned_files_count += 1
            total_lambdas += result['total']
            total_captureless += result['captureless']
            total_captureless_single += result['captureless_single_expr']

            if verbose and result['total'] > 0:
                print(f"\n[{result['filepath']}] - Found {result['total']} lambdas:")
                for l in result['lambdas']:
                    cap_type = "captureless" if l['captureless'] else "captured"
                    expr_type = "single-expression" if l['single_expression'] else "multi-statement"
                    print(f"  - Lambda starting at pos {l['start_pos']}: {cap_type}, {expr_type}")

            if scanned_files_count % 1000 == 0 or scanned_files_count == num_files:
                elapsed = time.time() - start_time
                print(f"Processed {scanned_files_count}/{num_files} files... ({elapsed:.1f}s)")

    elapsed_time = time.time() - start_time
    
    return {
        'dir': repo_dir,
        'scanned_files_count': scanned_files_count,
        'elapsed_time': elapsed_time,
        'error_files_count': len(error_files),
        'total_lambdas': total_lambdas,
        'total_captureless': total_captureless,
        'total_captureless_single': total_captureless_single
    }

def main():
    parser = argparse.ArgumentParser(description="Count lambda functions in a C++ codebase.")
    parser.add_argument('--repos', nargs='+', default=list(REPO_URLS.keys()), help='Directories to scan (clones automatically if known).')
    parser.add_argument('--test', action='store_true', help='Run self-tests.')
    parser.add_argument('-w', '--workers', type=int, default=None, help='Number of multiprocessing workers.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output.')
    args = parser.parse_args()

    if args.test:
        run_self_tests()
        return

    all_results = []

    for repo_dir in args.repos:
        if not os.path.exists(repo_dir):
            if repo_dir in REPO_URLS:
                url = REPO_URLS[repo_dir]
                print(f"Directory '{repo_dir}' does not exist. Cloning {url} from GitHub...")
                try:
                    subprocess.run(["git", "clone", "--depth", "1", url, repo_dir], check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Error: Failed to clone repository {repo_dir}: {e}")
                    continue
            else:
                print(f"Directory '{repo_dir}' does not exist and no known URL to clone. Skipping.")
                continue

        res = analyze_directory(repo_dir, args.workers, args.verbose)
        if res:
            all_results.append(res)

    print("\n" + "="*50)
    print("ANALYSIS RESULTS")
    print("="*50)
    
    grand_total_lambdas = 0
    grand_total_captureless = 0
    grand_total_captureless_single = 0
    
    for res in all_results:
        print(f"Directory Scanned:       {res['dir']}")
        print(f"Total C++ Files Scanned: {res['scanned_files_count']}")
        print(f"Total Execution Time:    {res['elapsed_time']:.2f} seconds")
        print(f"Failed to Read Files:    {res['error_files_count']}")
        print("-" * 40)
        print(f"Total Lambdas Found:     {res['total_lambdas']}")
        
        grand_total_lambdas += res['total_lambdas']
        grand_total_captureless += res['total_captureless']
        grand_total_captureless_single += res['total_captureless_single']
        
        if res['total_lambdas'] > 0:
            print(f"Captureless Lambdas:     {res['total_captureless']} ({res['total_captureless'] / res['total_lambdas'] * 100:.2f}% of total)")
            print(f"Captureless Single-Expr: {res['total_captureless_single']} ({res['total_captureless_single'] / res['total_lambdas'] * 100:.2f}% of total)")
            if res['total_captureless'] > 0:
                print(f"                         ({res['total_captureless_single'] / res['total_captureless'] * 100:.2f}% of captureless)")
        else:
            print("Captureless Lambdas:     0")
            print("Captureless Single-Expr: 0")
        print("="*50)

    if len(all_results) > 1:
        print("\n" + "="*50)
        print("GRAND TOTAL")
        print("="*50)
        print(f"Total Lambdas Found:     {grand_total_lambdas}")
        if grand_total_lambdas > 0:
            print(f"Captureless Lambdas:     {grand_total_captureless} ({grand_total_captureless / grand_total_lambdas * 100:.2f}% of total)")
            print(f"Captureless Single-Expr: {grand_total_captureless_single} ({grand_total_captureless_single / grand_total_lambdas * 100:.2f}% of total)")
            if grand_total_captureless > 0:
                print(f"                         ({grand_total_captureless_single / grand_total_captureless * 100:.2f}% of captureless)")
        else:
            print("Captureless Lambdas:     0")
            print("Captureless Single-Expr: 0")
        print("="*50)

if __name__ == '__main__':
    main()
