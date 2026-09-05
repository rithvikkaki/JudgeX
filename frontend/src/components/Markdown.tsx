import { Fragment, type ReactNode } from "react";

/**
 * A deliberately tiny Markdown subset for problem statements.
 *
 * Problem text is authored by administrators, but it is still rendered into
 * React elements rather than injected with `dangerouslySetInnerHTML` — so a
 * statement can never introduce script or markup into the page. Supporting a
 * handful of inline forms avoids pulling a full parser (and its sanitiser)
 * into the bundle for what is essentially bold, code and bullets.
 *
 * Supported: `**bold**`, `*italic*`, `` `code` ``, `- ` bullets, blank-line
 * paragraphs. Everything else renders as literal text.
 */
export function Markdown({ text }: { text: string }) {
  const blocks = text.replace(/\r\n/g, "\n").split(/\n{2,}/);

  return (
    <>
      {blocks.map((block, index) => {
        const lines = block.split("\n");
        const isList = lines.every((line) => /^\s*[-*]\s+/.test(line));

        if (isList) {
          return (
            <ul key={index} className="my-2 ml-4 list-disc space-y-1">
              {lines.map((line, lineIndex) => (
                <li key={lineIndex}>
                  <Inline text={line.replace(/^\s*[-*]\s+/, "")} />
                </li>
              ))}
            </ul>
          );
        }

        return (
          <p key={index} className={index > 0 ? "mt-3" : undefined}>
            {lines.map((line, lineIndex) => (
              <Fragment key={lineIndex}>
                {lineIndex > 0 && <br />}
                <Inline text={line} />
              </Fragment>
            ))}
          </p>
        );
      })}
    </>
  );
}

// Ordered so that `**bold**` is consumed before the single-asterisk italic
// rule can match its delimiters.
const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\n]+\*)/g;

function Inline({ text }: { text: string }) {
  const parts = text.split(INLINE).filter(Boolean);

  return (
    <>
      {parts.map((part, index): ReactNode => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={index} className="font-semibold text-violet-50">
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code
              key={index}
              className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[0.9em] text-violet-100"
            >
              {part.slice(1, -1)}
            </code>
          );
        }
        if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
          return (
            <em key={index} className="italic">
              {part.slice(1, -1)}
            </em>
          );
        }
        return <Fragment key={index}>{part}</Fragment>;
      })}
    </>
  );
}
