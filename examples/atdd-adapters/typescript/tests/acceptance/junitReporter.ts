/**
 * A JUnit reporter for node:test that names each test's file.
 *
 * node's own JUnit reporter gives every testcase the classname "test", so a
 * report cannot tell two tests with one name in two files apart. This one
 * writes the file's path, relative to the folder the run started in, as the
 * classname. A scenario then binds to `<file>::<test name>`, the file and the
 * name together. The failure's `type` is node's failure type, such as
 * `hookFailed` for a failed `beforeEach` hook, and its text is the error with
 * its cause, as node prints it. A describe block is not a testcase: its tests
 * are.
 *
 * `run.ts` passes it to node as `--test-reporter=./tests/acceptance/junitReporter.ts`.
 */
import { relative } from "node:path";
import { inspect } from "node:util";

interface TestEvent {
  type: string;
  data: {
    name: string;
    file?: string;
    skip?: boolean | string;
    todo?: boolean | string;
    details?: { duration_ms?: number; type?: string; error?: { failureType?: string; message?: string } };
  };
}

function escape(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;")
    // Characters XML 1.0 cannot hold, such as the colour codes of a terminal.
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "");
}

export default async function* junitReporter(source: AsyncIterable<TestEvent>): AsyncGenerator<string> {
  const cases: string[] = [];
  for await (const event of source) {
    if ((event.type !== "test:pass" && event.type !== "test:fail") || event.data.details?.type === "suite") {
      continue;
    }
    const { name, file, skip, todo, details } = event.data;
    const classname = file ? relative(process.cwd(), file).split("\\").join("/") : "test";
    const seconds = ((details?.duration_ms ?? 0) / 1000).toFixed(6);
    const open = `\t<testcase name="${escape(name)}" classname="${escape(classname)}" time="${seconds}"`;
    if (event.type === "test:fail") {
      const error = details?.error;
      const type = escape(error?.failureType ?? "testCodeFailure");
      const message = escape(error?.message ?? "");
      cases.push(`${open}>\n\t\t<failure type="${type}" message="${message}">\n`
        + `${escape(inspect(error, { depth: 4 }))}\n\t\t</failure>\n\t</testcase>`);
    } else if (skip !== undefined && skip !== false || todo !== undefined && todo !== false) {
      cases.push(`${open}>\n\t\t<skipped/>\n\t</testcase>`);
    } else {
      cases.push(`${open}/>`);
    }
  }
  yield `<?xml version="1.0" encoding="utf-8"?>\n<testsuites>\n${cases.join("\n")}\n</testsuites>\n`;
}
