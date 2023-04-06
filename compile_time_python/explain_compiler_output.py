import re, sys
import colors
from compiler_explanations import get_explanation

from llm_explainer import explain_dcc_output_via_llm

ANSI_DEFAULT = "\033[0m"


def explain_compiler_output(output, args):
    lines = output.splitlines()
    print(lines)
    explanations_made = set()
    errors_explained = 0
    last_message = None
    if args.colorize_output:
        color = colors.color
    else:
        color = lambda text, color_name: text

    while lines and (
        not errors_explained or len(explanations_made) < args.max_explanations
    ):
        message, lines = get_next_message(lines)
        if args.debug > 2:
            print("message", message, file=sys.stderr)
        if not message:
            print(lines.pop(0), file=sys.stderr)
            continue

        if (
            last_message
            and message.is_same_line(last_message)
            and (last_message.type == "error" or message.type == "warning")
        ):
            # skip if there are two errors for one line
            # often the second message is unhelpful
            if args.debug:
                print("skipping subsequent compiler messages for line", file=sys.stderr)
            continue

        if (
            message.type == "warning"
            and len(explanations_made) >= args.max_explanations
        ):
            # skip warnings if we have made max_explanations
            # we don't exit because we want to print the first error if there is one
            if args.debug:
                print(
                    "skipping warning because of number of explanations already made",
                    file=sys.stderr,
                )
            continue

        # dcc use -D on command-line for several purposes
        # e.g -Dread=__real_read to avoid a user-defined read being called from dcc's own code
        # so we tidy error mentioning such names to hide this

        text = "\n".join(message.text_without_ansi_codes)

        for prefix in ["__renamed_", "__real_", "__wrap_"]:
            if prefix in text:
                message.text = [s.replace(prefix, "") for s in message.text]
                message.text_without_ansi_codes = [
                    s.replace(prefix, "") for s in message.text_without_ansi_codes
                ]
                # note may mention command line arguments
                message.note = []
                message.note_without_ansi_codes = []

        last_message = message

        if args.debug:
            print(
                "message for explanation:",
                message.text_without_ansi_codes,
                file=sys.stderr,
            )

        explanation = get_explanation(message, args.colorize_output)
        explanation_text = ""
        if explanation:
            explanation_text = explanation.text.rstrip("\n")

        if args.debug:
            print("explanation_text:", explanation_text, file=sys.stderr)

        message_lines = message.text
        if not explanation or explanation.show_note:
            message_lines += message.note

        text = "\n".join(message_lines)
        if message.has_ansi_codes():
            text += ANSI_DEFAULT
        print(text, file=sys.stderr)

        if not explanation_text:
            continue  # should we give up when we get a message for which we don't have an explanation?

        # remove any reference to specific line and check if we've already made this explanation
        e = re.sub("line.*", "", explanation_text, flags=re.I)
        if e in explanations_made:
            continue
        explanations_made.add(e)

        if message.type == "error":
            errors_explained += 1

        prefix = color("dcc explanation:", "cyan")
        print(prefix, explanation_text, file=sys.stderr)

        if explanation and explanation.no_following_explanations:
            if args.debug:
                print(
                    "printing no further compiler messages because explanation.no_following_explanations set"
                )
            break
    if lines and lines[-1].endswith(" generated."):
        lines[-1] = re.sub(r"\d .*", "", lines[-1])

    # if we explained 1 or more errors, don't output any remaining compiler output
    # often its confusing parasitic errors
    #
    # if we didn't explain any messages, just pass through all compiler output
    #
    if not errors_explained:
        print("\n".join(lines), file=sys.stderr)


class Message:
    file = ""
    line_number = ""
    column = ""
    type = ""
    text = []
    text_without_ansi_codes = []
    note = []
    note_without_ansi_codes = []
    highlighted_word = ""
    underlined_word = ""

    def is_same_line(self, message):
        return message and (message.file, message.line_number) == (
            self.file,
            self.line_number,
        )

    def has_ansi_codes(self):
        return (
            self.text != self.text_without_ansi_codes
            or self.note != self.note_without_ansi_codes
        )

    def __str__(self):
        t = self.text_without_ansi_codes
        h = self.highlighted_word
        u = self.underlined_word
        return f"Message(text_without_ansi_codes='{t}', highlighted_word='{h}', underlined_word='{u}')"


def get_next_message(lines):
    if not lines:
        return (None, lines)
    line = lines[0]
    colorless_line = convert_smart_quotes_to_dumb_quotes(colors.strip_color(line))
    m = re.match(r"^(\S.*?):(\d+):", colorless_line)
    if not m:
        return (None, lines)
    lines.pop(0)
    e = Message()
    e.file, e.line_number = m.groups()
    m = re.match(r"^\S.*?:\d+:(\d+):\s*(.*?):", colorless_line)
    if m:
        e.column, e.type = m.groups()

    e.text = [line]
    e.text_without_ansi_codes = [colorless_line]
    parsing_note = False

    while lines:
        next_line = lines[0]
        if not next_line:
            break
        colorless_next_line = colors.strip_color(lines[0])
        m = re.match(r"^\S.*:\d+:", colorless_next_line)
        if m:
            if re.match(r"^\S.*?:\d+:\d+:\s*note:", colorless_next_line):
                parsing_note = True
            else:
                break

        lines.pop(0)

        if colorless_next_line.endswith(" generated."):
            break

        if parsing_note:
            e.note.append(next_line)
            e.note_without_ansi_codes.append(colorless_next_line)
            continue

        if re.match(r"^[ ~\d|]*\^[ ~]*$", colorless_next_line):
            previous_line = e.text_without_ansi_codes[-1]
            m = re.match(r"^(.*)\^~+", colorless_next_line)
            if m:
                e.highlighted_word = previous_line[len(m.group(1)) : len(m.group(0))]
            else:
                caret_index = colorless_next_line.index("^")
                m = re.match(r"^\w*", previous_line[caret_index:])
                e.highlighted_word = m.group(0)

            e.underlined_word = ""
            m = re.match(r"^(.*?)~+", colorless_next_line)
            if m:
                e.underlined_word = previous_line[len(m.group(1)) : len(m.group(0))]

        e.text.append(next_line)
        e.text_without_ansi_codes.append(colorless_next_line)

    return (e, lines)


def convert_smart_quotes_to_dumb_quotes(string):
    string = string.replace("\u2018", "'")
    string = string.replace("\u2019", "'")
    string = string.replace("\u201C", '"')
    string = string.replace("\u201D", '"')
    return string
