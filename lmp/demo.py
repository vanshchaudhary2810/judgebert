"""Interactive Gradio demo for presentations: paste an original + simplified clause, get the full output."""
from .config import Config
from .explain import explain_pair


def launch_demo(model, tokenizer, cfg: Config, share: bool = True, launch: bool = True):
    import gradio as gr

    def run(original, simplified, lang):
        ex = explain_pair(model, tokenizer, original, simplified, lang, cfg)
        attr = ex["attributions"]["simplified"] if ex["attributions"] else []
        m = max([abs(s) for _, s in attr] + [1e-9])
        highlighted = [(w + " ", round(float(s) / m, 3)) for w, s in attr]   # in [-1, 1] for colouring
        probs = {k: v for k, v in ex["error_probs"].items()}
        return f"{ex['lmp_score']:.1f} / 10", ex["decision"], probs, highlighted, ex["explanation"]

    examples = [
        ["The Insured shall notify the Insurer in writing of any loss within 30 days of its occurrence, failing which the claim shall not be admissible.",
         "The insured may tell the insurer about any loss within 30 days.", "en"],
        ["The Tenant shall not sublet, assign or part with possession of the premises or any part thereof without the prior written consent of the Landlord.",
         "The tenant must not sublet any part of the premises without the landlord's written permission.", "en"],
        ["किरायेदार प्रत्येक कैलेंडर माह की 5 तारीख को या उससे पूर्व रु. 25,000 का मासिक किराया अदा करेगा।",
         "किरायेदार को हर महीने की 10 तारीख तक रु. 25,000 किराया देना होगा।", "hi"],
    ]
    demo = gr.Interface(
        fn=run,
        inputs=[gr.Textbox(label="Original legal text", lines=4), gr.Textbox(label="Simplified text", lines=4),
                gr.Radio(["en", "hi"], value="en", label="Language")],
        outputs=[gr.Textbox(label="LMP score"), gr.Textbox(label="Decision"),
                 gr.Label(label="Legal error-type probabilities", num_top_classes=9),
                 gr.HighlightedText(label="Word attributions in the simplification (red = lowered the score)"),
                 gr.Textbox(label="Explanation", lines=5)],
        examples=examples, title="Explainable Multilingual Legal Meaning Preservation",
        description="JUDGEBERT-style cross-encoder extended to English + Hindi with error types and explanations.")
    return demo.launch(share=share) if launch else demo
