/**
 * The layers keep their shape.
 *
 * This test reads the source of the DSL and of the specifications with the
 * TypeScript compiler's parser; it does not run them, and it needs no running
 * system. Each breach it finds is reported as `<file>:<line>: <rule>: <what it
 * found>`, with the file relative to the example's root. One test per rule:
 *
 * - the DSL makes no check: no `throw`, no call to `assert` or `expect` and
 *   no call to a `fail` inside the DSL file. A check belongs in the driver;
 * - every identifier goes through an alias: a string in a specification that
 *   matches a pattern in IDENTIFIER_PATTERNS must be an argument of a DSL
 *   method parameter that the method passes to `this.alias(...)`;
 * - one DSL call per Given, When or Then line: each statement of a scenario is
 *   one DSL call, and the calls match the step lines of the comment at the top
 *   of the scenario. Lines and calls are matched in three phases: a Given line
 *   (and the And lines after it) to a method whose name starts `has`, a Then
 *   line (and its And lines) to one that starts `confirm`, a When line (and
 *   its And lines) to any other. Within a phase, lines and calls are matched
 *   by count. The rule reads each top-level `test(...)` call of a
 *   specification file;
 * - a DSL method name uses no banned term: the words of each DSL method name
 *   must not hold a term of the `banned` list in the project's
 *   `governance/terminology.yml`, the first one found in the example's root
 *   or a folder above it. Without that file the rule skips and says why.
 *
 * To adopt it, set the paths, the identifier patterns and, if your banned list
 * is elsewhere, TERMINOLOGY_FILE below for your suite.
 */
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { parse } from "yaml";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const ROOT = fileURLToPath(new URL("../..", import.meta.url));
const DSL_FILE = join(HERE, "dsl.ts");
const SPEC_FILES = readdirSync(HERE).filter((f) => f.endsWith(".spec.ts")).sort().map((f) => join(HERE, f));

/** The identifiers a specification must name only through the DSL's alias helper. */
const IDENTIFIER_PATTERNS: Record<string, RegExp> = {
  "email address": /[\w.+-]+@[\w-]+(\.[\w-]+)+/,
};

/** The project's vocabulary file: the first one in the example's root or a folder above it. */
function findTerminology(): string | null {
  for (let folder = ROOT; ; folder = dirname(folder)) {
    const candidate = join(folder, "governance", "terminology.yml");
    if (existsSync(candidate)) {
      return candidate;
    }
    if (dirname(folder) === folder) {
      return null;
    }
  }
}
const TERMINOLOGY_FILE = findTerminology();

const RULE_NO_CHECK = "the DSL makes no check";
const RULE_ALIAS = "every identifier goes through an alias";
const RULE_ONE_CALL = "one DSL call per Given, When or Then line";
const RULE_BANNED = "a DSL method name uses no banned term";

const STEP = /^\s*(Given|When|Then|And)\b\s*(.*?)\s*$/;
type Phase = "Given" | "When" | "Then";

function source(path: string): ts.SourceFile {
  return ts.createSourceFile(path, readFileSync(path, "utf8"), ts.ScriptTarget.Latest, true);
}

function rel(path: string): string {
  return relative(ROOT, path).split("\\").join("/");
}

function lineOf(file: ts.SourceFile, position: number): number {
  return file.getLineAndCharacterOfPosition(position).line + 1;
}

function report(breaches: string[]): string {
  return "\n" + breaches.join("\n");
}

function walk(node: ts.Node, visit: (node: ts.Node) => void): void {
  visit(node);
  node.forEachChild((child) => walk(child, visit));
}

// --- reading the DSL -----------------------------------------------------------

function dslMethods(file: ts.SourceFile): [ts.ClassDeclaration, ts.MethodDeclaration][] {
  const found: [ts.ClassDeclaration, ts.MethodDeclaration][] = [];
  for (const statement of file.statements) {
    if (ts.isClassDeclaration(statement)) {
      for (const member of statement.members) {
        if (ts.isMethodDeclaration(member)) {
          found.push([statement, member]);
        }
      }
    }
  }
  return found;
}

function nameOf(node: { name?: ts.PropertyName | ts.Identifier }): string {
  return node.name && (ts.isIdentifier(node.name) || ts.isStringLiteral(node.name)) ? node.name.text : "?";
}

/** The function, method or class a node is inside, for the breach message. */
function owner(node: ts.Node): string {
  const parts: string[] = [];
  for (let at: ts.Node | undefined = node.parent; at; at = at.parent) {
    if (ts.isMethodDeclaration(at) || ts.isFunctionDeclaration(at) || ts.isClassDeclaration(at)) {
      parts.unshift(nameOf(at));
    }
  }
  return parts.join(".") || "the DSL file";
}

/** The parameters `method` passes to `this.alias(...)`. */
function aliasedParameters(method: ts.MethodDeclaration): Set<string> {
  const found = new Set<string>();
  walk(method, (node) => {
    if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)
        && node.expression.expression.kind === ts.SyntaxKind.ThisKeyword
        && node.expression.name.text === "alias" && node.arguments.length > 0
        && ts.isIdentifier(node.arguments[0])) {
      found.add(node.arguments[0].text);
    }
  });
  return found;
}

type Shape = Map<string, Map<string, { parameters: string[]; aliased: Set<string> }>>;

/** {part: {method: (parameters, aliased parameters)}}, the parts read from the assignments `this.<part> = new <Class>(...)`. */
function dslShape(file: ts.SourceFile): Shape {
  const classes = new Map<string, Map<string, { parameters: string[]; aliased: Set<string> }>>();
  for (const [cls, method] of dslMethods(file)) {
    const methods = classes.get(nameOf(cls)) ?? new Map();
    methods.set(nameOf(method), {
      parameters: method.parameters.map((p) => (ts.isIdentifier(p.name) ? p.name.text : "?")),
      aliased: aliasedParameters(method),
    });
    classes.set(nameOf(cls), methods);
  }
  const parts: Shape = new Map();
  walk(file, (node) => {
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.EqualsToken
        && ts.isPropertyAccessExpression(node.left) && node.left.expression.kind === ts.SyntaxKind.ThisKeyword
        && ts.isNewExpression(node.right) && ts.isIdentifier(node.right.expression)
        && classes.has(node.right.expression.text)) {
      parts.set(node.left.name.text, classes.get(node.right.expression.text)!);
    }
  });
  return parts;
}

// --- reading the specifications -------------------------------------------------

function rootName(expression: ts.Expression): string | null {
  let at: ts.Expression = expression;
  while (ts.isPropertyAccessExpression(at) || ts.isCallExpression(at)) {
    at = at.expression;
  }
  return ts.isIdentifier(at) ? at.text : null;
}

/** The calls inside `node` whose callee starts at the name `dsl`. */
function dslCalls(node: ts.Node): ts.CallExpression[] {
  const found: ts.CallExpression[] = [];
  walk(node, (at) => {
    if (ts.isCallExpression(at) && rootName(at.expression) === "dsl") {
      found.push(at);
    }
  });
  return found;
}

/** ['todo', 'add'] for `dsl.todo.add(...)`, else null. */
function partAndMethod(call: ts.CallExpression): [string, string] | null {
  const callee = call.expression;
  if (ts.isPropertyAccessExpression(callee) && ts.isPropertyAccessExpression(callee.expression)
      && ts.isIdentifier(callee.expression.expression) && callee.expression.expression.text === "dsl") {
    return [callee.expression.name.text, callee.name.text];
  }
  return null;
}

/** [name, body] of each top-level `test(name, () => { ... })` of a specification file. */
function scenarios(file: ts.SourceFile): [string, ts.Block][] {
  const found: [string, ts.Block][] = [];
  for (const statement of file.statements) {
    if (ts.isExpressionStatement(statement) && ts.isCallExpression(statement.expression)
        && ts.isIdentifier(statement.expression.expression)
        && ["test", "it"].includes(statement.expression.expression.text)) {
      const [title, body] = statement.expression.arguments;
      if (body && (ts.isArrowFunction(body) || ts.isFunctionExpression(body)) && ts.isBlock(body.body)) {
        found.push([title && ts.isStringLiteral(title) ? title.text : "?", body.body]);
      }
    }
  }
  return found;
}

/** [[phase, text, line]] from the comment at the top of a scenario's body. */
function steps(file: ts.SourceFile, body: ts.Block): [Phase, string, number][] {
  const text = file.getFullText();
  const start = body.getStart(file) + 1;
  const end = body.statements.length ? body.statements[0].getStart(file) : body.getEnd() - 1;
  const found: [Phase, string, number][] = [];
  let phase: Phase = "Given";
  const lines = text.slice(start, end).split("\n");
  lines.forEach((line, offset) => {
    const step = STEP.exec(line.replace(/^\s*(\/\*+|\*+\/?|\/\/)/, ""));
    if (step) {
      const [, keyword, rest] = step;
      if (keyword !== "And") {
        phase = keyword as Phase;
      }
      found.push([phase, `${keyword} ${rest}`.replace(/\s*\*\/$/, ""), lineOf(file, start) + offset]);
    }
  });
  return found;
}

function phaseOfMethod(method: string): Phase {
  if (method.startsWith("has")) {
    return "Given";
  }
  return method.startsWith("confirm") ? "Then" : "When";
}

// --- reading the banned list -------------------------------------------------------

/** The lower-case words of a name or a term: `routeTodo` gives ['route', 'todo']. */
function words(text: string): string[] {
  return (text.replace(/([a-z0-9])([A-Z])/g, "$1 $2").match(/[A-Za-z0-9]+/g) ?? []).map((w) => w.toLowerCase());
}

function bannedTerms(path: string): [string, string[]][] {
  const entries = (parse(readFileSync(path, "utf8"))?.banned ?? []) as { term?: string }[];
  return entries.flatMap((entry) => String(entry.term ?? "").split("/"))
    .map((term): [string, string[]] => [term.trim(), words(term)])
    .filter(([, termWords]) => termWords.length > 0);
}

function holds(nameWords: string[], termWords: string[]): boolean {
  for (let i = 0; i + termWords.length <= nameWords.length; i++) {
    if (termWords.every((word, j) => nameWords[i + j] === word)) {
      return true;
    }
  }
  return false;
}

// --- the rules ----------------------------------------------------------------------

test("the DSL makes no check", () => {
  const file = source(DSL_FILE);
  const breaches: string[] = [];
  walk(file, (node) => {
    let found: string | null = null;
    if (ts.isThrowStatement(node)) {
      found = "a thrown exception";
    } else if (ts.isCallExpression(node)) {
      const callee = node.expression;
      const name = ts.isIdentifier(callee) ? callee.text : ts.isPropertyAccessExpression(callee) ? callee.name.text : "";
      const root = rootName(callee);
      if (root === "assert" || root === "expect") {
        found = `a call to ${callee.getText(file)}`;
      } else if (name === "fail") {
        found = "a call to the runner's fail";
      }
    }
    if (found) {
      breaches.push(`${rel(DSL_FILE)}:${lineOf(file, node.getStart(file))}: ${RULE_NO_CHECK}: ${found} in `
        + `${owner(node)}; the check belongs in the driver`);
    }
  });
  assert.deepEqual(breaches, [], report(breaches));
});

test("every identifier goes through an alias", () => {
  const shape = dslShape(source(DSL_FILE));
  const breaches: string[] = [];
  for (const path of SPEC_FILES) {
    const file = source(path);
    const aliased = new Set<ts.Node>();
    for (const call of dslCalls(file)) {
      const target = partAndMethod(call);
      const method = target && shape.get(target[0])?.get(target[1]);
      if (!method) {
        continue;
      }
      call.arguments.forEach((argument, i) => {
        if (method.aliased.has(method.parameters[i])) {
          aliased.add(argument);
        }
      });
    }
    walk(file, (node) => {
      if ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) && !aliased.has(node)) {
        for (const [kind, pattern] of Object.entries(IDENTIFIER_PATTERNS)) {
          if (pattern.test(node.text)) {
            breaches.push(`${rel(path)}:${lineOf(file, node.getStart(file))}: ${RULE_ALIAS}: the ${kind} `
              + `'${node.text}' reaches no DSL parameter that aliases it`);
          }
        }
      }
    });
  }
  assert.deepEqual(breaches, [], report(breaches));
});

test("one DSL call per Given, When or Then line", () => {
  const breaches: string[] = [];
  for (const path of SPEC_FILES) {
    const file = source(path);
    for (const [title, body] of scenarios(file)) {
      const calls: Record<Phase, number[]> = { Given: [], When: [], Then: [] };
      for (const statement of body.statements) {
        const at = lineOf(file, statement.getStart(file));
        const found = dslCalls(statement);
        let expression = ts.isExpressionStatement(statement) ? statement.expression : null;
        if (expression && ts.isAwaitExpression(expression)) {
          expression = expression.expression;
        }
        if (!expression || !ts.isCallExpression(expression) || found[0] !== expression) {
          breaches.push(`${rel(path)}:${at}: ${RULE_ONE_CALL}: this statement is not a DSL call`);
          continue;
        }
        if (found.length > 1) {
          breaches.push(`${rel(path)}:${at}: ${RULE_ONE_CALL}: one statement makes ${found.length} DSL calls`);
          continue;
        }
        calls[phaseOfMethod(partAndMethod(expression)?.[1] ?? "")].push(at);
      }
      const lines: Record<Phase, [string, number][]> = { Given: [], When: [], Then: [] };
      for (const [phase, text, line] of steps(file, body)) {
        lines[phase].push([text, line]);
      }
      if (!Object.values(lines).some((l) => l.length)) {
        breaches.push(`${rel(path)}:${lineOf(file, body.getStart(file))}: ${RULE_ONE_CALL}: '${title}' has no `
          + "scenario in the comment at its top");
        continue;
      }
      for (const phase of ["Given", "When", "Then"] as const) {
        const asked = lines[phase];
        const made = calls[phase];
        if (made.length > asked.length) {
          if (asked.length) {
            const [text, line] = asked[asked.length - 1];
            const shared = made.slice(asked.length - 1);
            for (const at of made.slice(asked.length)) {
              breaches.push(`${rel(path)}:${at}: ${RULE_ONE_CALL}: the line '${text}' (line ${line}) makes `
                + `${shared.length} DSL calls, at lines ${shared.join(", ")}`);
            }
          } else {
            for (const at of made) {
              breaches.push(`${rel(path)}:${at}: ${RULE_ONE_CALL}: a DSL call that no ${phase} line asks for`);
            }
          }
        }
        for (const [text, line] of asked.slice(made.length)) {
          breaches.push(`${rel(path)}:${line}: ${RULE_ONE_CALL}: the line '${text}' makes no DSL call`);
        }
      }
    }
  }
  assert.deepEqual(breaches, [], report(breaches));
});

test("no DSL method name uses a banned term", (t) => {
  if (TERMINOLOGY_FILE === null) {
    t.skip("no governance/terminology.yml in the example's root or a folder above it, so there is no "
      + "banned list to check the DSL's method names against");
    return;
  }
  const terms = bannedTerms(TERMINOLOGY_FILE);
  const file = source(DSL_FILE);
  const breaches: string[] = [];
  for (const [cls, method] of dslMethods(file)) {
    const nameWords = words(nameOf(method));
    for (const [term, termWords] of terms) {
      if (holds(nameWords, termWords)) {
        breaches.push(`${rel(DSL_FILE)}:${lineOf(file, method.getStart(file))}: ${RULE_BANNED}: the method `
          + `${nameOf(cls)}.${nameOf(method)} uses the banned term '${term}' of governance/terminology.yml`);
      }
    }
  }
  assert.deepEqual(breaches, [], report(breaches));
});
