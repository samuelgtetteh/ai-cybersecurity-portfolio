"""Cloud Target Lab — scenario explorer (a Space can't run LocalStack, so this shows the seeded
resource catalog the lab uses to test cloud scanners)."""
import gradio as gr
import pandas as pd

df = pd.read_csv("scenarios.csv")

with gr.Blocks(title="Cloud Target Lab") as demo:
    gr.Markdown(
        "# ☁️ Cloud Target Lab — seeded scenario catalog\n"
        "The [cloud-target-lab](https://github.com/samuelgtetteh/cloud-target-lab) stands up a "
        "LocalStack fake-AWS seeded with these mixed secure/insecure resources to test cloud "
        "security scanners. A Space can't run LocalStack, so this just shows the catalog — run the "
        "lab locally (GitHub) to stand up the live environment.")
    gr.Dataframe(df, label="seeded resources (posture + expected finding)")

demo.launch()
