import { useMemo } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { python } from "@codemirror/lang-python";
import { cpp } from "@codemirror/lang-cpp";
import { java } from "@codemirror/lang-java";
import { oneDark } from "@codemirror/theme-one-dark";
import type { LanguageId } from "../lib/types";

/** Runnable skeletons so a new user is never staring at an empty buffer. */
export const STARTERS: Record<LanguageId, string> = {
  python: `# Read from standard input, write to standard output.
a, b = map(int, input().split())
print(a + b)
`,
  cpp: `#include <iostream>

int main() {
    long long a, b;
    std::cin >> a >> b;
    std::cout << a + b << std::endl;
    return 0;
}
`,
  java: `import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        long a = scanner.nextLong();
        long b = scanner.nextLong();
        System.out.println(a + b);
    }
}
`,
};

export function CodeEditor({
  value,
  onChange,
  language,
  height = "420px",
}: {
  value: string;
  onChange: (value: string) => void;
  language: LanguageId;
  height?: string;
}) {
  const extensions = useMemo(() => {
    switch (language) {
      case "cpp":
        return [cpp()];
      case "java":
        return [java()];
      default:
        return [python()];
    }
  }, [language]);

  return (
    <CodeMirror
      value={value}
      height={height}
      theme={oneDark}
      extensions={extensions}
      onChange={onChange}
      basicSetup={{
        lineNumbers: true,
        highlightActiveLine: true,
        highlightActiveLineGutter: true,
        bracketMatching: true,
        closeBrackets: true,
        autocompletion: true,
        foldGutter: false,
        // The browser's own search UI is more familiar than CodeMirror's,
        // and the panel fights the glass styling.
        searchKeymap: false,
      }}
      aria-label="Source code editor"
    />
  );
}
