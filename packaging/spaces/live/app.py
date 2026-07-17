"""Live Target Lab — a Gradio demo of the synthetic events the lab streams to the detectors.
(The real lab runs as standing Docker services and reports ground-truth feedback; this Space just
lets you preview the kind of data it generates.)"""
import random

import gradio as gr
import pandas as pd

import identity_generator as ig   # bundled; its streaming loop is under __main__ so import is safe
import ics_generator as ic


def gen_identity(n):
    rows = []
    for _ in range(int(n)):
        if random.random() < 0.15:
            ev = ig.make_attack_event(random.choice(ig.SUSPICIOUS_USERS), random.choice(ig.NORMAL_PCS))
            ev["injected_label"] = "malicious (suspicious)"
        else:
            ev = ig.make_normal_event()
            ev["injected_label"] = "benign"
        rows.append(ev)
    return pd.DataFrame(rows)


def gen_ics(n):
    rows = []
    for _ in range(int(n)):
        r, attack = ic.generate_reading()
        rows.append({"P1_FT01": round(r["P1_FT01"], 2), "P1_TIT01": round(r["P1_TIT01"], 2),
                     "P1_PIT01": round(r["P1_PIT01"], 3), "P2_On": r["P2_On"],
                     "injected_label": "malicious (spike)" if attack else "benign"})
    return pd.DataFrame(rows)


with gr.Blocks(title="Live Target Lab") as demo:
    gr.Markdown(
        "# 🛰️ Live Target Lab — synthetic event generator\n"
        "Preview the synthetic **identity** and **OT/ICS** events the "
        "[live-target-lab](https://github.com/samuelgtetteh/live-target-lab) streams to the "
        "detectors. ~15% are intentionally suspicious (labelled). Pairs with the models "
        "[`stetteh/identity-anomaly`](https://huggingface.co/stetteh/identity-anomaly) and "
        "[`stetteh/otics-anomaly`](https://huggingface.co/stetteh/otics-anomaly).")
    with gr.Tab("Identity login events"):
        n1 = gr.Slider(5, 100, value=20, step=5, label="how many events")
        gr.Button("Generate").click(gen_identity, n1, gr.Dataframe(label="events"))
    with gr.Tab("OT/ICS sensor readings"):
        n2 = gr.Slider(5, 100, value=20, step=5, label="how many readings")
        gr.Button("Generate").click(gen_ics, n2, gr.Dataframe(label="readings (subset of 59 tags)"))

demo.launch()
