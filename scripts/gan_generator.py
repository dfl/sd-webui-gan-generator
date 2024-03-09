import modules.scripts as scripts
import gradio as gr
from glob import glob
from pathlib import Path

from modules import script_callbacks
import json
import re

import gradio as gr
import numpy as np

from scripts.model import Model

import torch
import random

from modules import ui
from modules.ui_components import ToolButton
ui.swap_symbol = "\U00002194"  # ↔️

model = Model()

DESCRIPTION = '''# StyleGAN3 Simple Image Generator Extension

Use this tool to generate random images with a pretrained StyleGAN3 network of your choice. 
Download model pickle files and place them in sd-webui-gan-generator/models folder. 
Supports generation with the cpu or gpu0. See available pretrained networks via [https://github.com/NVlabs/stylegan3](https://github.com/NVlabs/stylegan3).
Recommend using stylegan3-r-ffhq or stylegan2-celebahq
'''
def swap_slider(slider1, slider2):
    return slider2, slider1
    
def random_seeds(slider1, slider2, slider3):
    return random.randint(0, 0xFFFFFFFF - 1), random.randint(0, 0xFFFFFFFF - 1), random.randint(0, 0xFFFFFFFF - 1)
    
def str2num(string):
    match = re.search(r'(\d+)', string)
    if match:
        number = int(match.group())
        return number
    else:
        return None

def copy_seed(outputSeed):
    number = str2num(outputSeed)
    if number is not None:
        return number

def update_model_list():
    path = Path(__file__).resolve().parents[1] / "models"
    return [Path(file).name for file in glob(str(path / "*.pkl"))]

def default_model():
    return update_model_list()[0] if update_model_list() else None

def update_model_drop():
    new_choices = gr.Dropdown.update(choices = update_model_list())
    return new_choices

def default_device():
    if torch.backends.mps.is_available():
        default_device = "mps"
    elif torch.cuda.is_available():
        default_device = "cuda:0"
    else:
        default_device = "cpu"
    return default_device

def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False, css='style.css') as ui_component:
        gr.Markdown(DESCRIPTION)
        with gr.Row():
            modelDrop = gr.Dropdown(choices = update_model_list(), value=default_model, label="Model Selection", info="Place into models directory")
            model_refresh_button = ToolButton(value=ui.refresh_symbol, tooltip="Refresh")
            deviceDrop = gr.Dropdown(choices = ['cpu','cuda:0','mps'], value=default_device, label='Generation Device', info='Generate using CPU or GPU')
                                
        with gr.Tabs():
            with gr.TabItem('Simple Image Gen'):
                with gr.Row():
                    with gr.Column():
                        psi = gr.Slider(0,
                                        2,
                                        step=0.05,
                                        value=0.7,
                                        label='Truncation psi')
                        with gr.Row():
                            seed = gr.Number(label='Seed', value=-1, min_width=150, precision=0)
                            random_seed = ToolButton(ui.random_symbol, tooltip="Set seed to -1, which will cause a new random number to be used every time")
                            random_seed.click(fn=lambda: seed.update(value=-1), show_progress=False, inputs=[], outputs=[seed])
                            reuse_seed = ToolButton(ui.reuse_symbol, tooltip="Reuse seed from last generation, mostly useful if it was randomized")
 
                        outputSeed = gr.Markdown(label='Output Seed')
                        simple_run_button = gr.Button('Generate Simple Image')

                    with gr.Column():
                        result = gr.Image(label='Result', elem_id='result')
                        outputSeed = gr.Markdown(label='Output Seed')
                        with gr.Row():
                            send_to_style_button1 = gr.Button('Send Seed to Style Mixer : Left')
                            send_to_style_button2 = gr.Button('Send Seed to Style Mixer : Right')

            with gr.TabItem('Style Mixer'):
                with gr.Row():
                    seed1 = gr.Number(label='Seed 1', value=0, min_width=150, precision=0)
                    seed2 = gr.Number(label='Seed 2', value=0, min_width=150, precision=0)
                    seed3 = gr.Number(label='Seed 3', value=0, min_width=150, precision=0)
                    random_seeds_button = ToolButton(ui.random_symbol, tooltip="Pick Seeds For Me", show_progress=False)

                psi_style = gr.Slider(0,
                                2,
                                step=0.05,
                                value=0.7,
                                label='Truncation psi')  
                with gr.Row():
                    styleDrop = gr.Dropdown(
                                choices=["coarse", "fine", "total"], label="Style Transfer Method A", value="coarse"
                                    ),                                        
                    style_interp = gr.Slider(0,
                                    2,
                                    step=0.01,
                                    value=1.0,
                                    label='Seed Interpolation A (Horiz. Cross-Fade)')
                    styleDrop2 = gr.Dropdown(
                                choices=["coarse", "fine", "total"], label="Style Transfer Method B", value="coarse"
                                    ),                                        
                    style_interp2 = gr.Slider(0,
                                    2,
                                    step=0.01,
                                    value=1.0,
                                    label='Seed Interpolation B (Vert. Cross-Fade)')
                                    
                    style_run_button = gr.Button('Generate Style Mix')

                with gr.Row():
                    with gr.Column():
                        seed1im = gr.Image(label='Seed 1 Image', elem_id='seed1')
                        seed1txt = gr.Markdown(label='Seed 1', value="",show_progress=False)
                    with gr.Column():
                        styleim = gr.Image(label='Style Mixed Image', elem_id='style')
                    with gr.Column():
                        seed2im = gr.Image(label='Seed 2 Image', elem_id='seed2')
                        seed2txt = gr.Markdown(label='Seed 2', value="",show_progress=False)
                with gr.Row():
                    blank1 = gr.Image(show_progress=False)
                    with gr.Column():
                        seed3im = gr.Image(label='Seed 3 Image', elem_id='seed3', scale=0)
                        seed3txt = gr.Markdown(label='Seed 3', value="",show_progress=False)
                    blank2 = gr.Image(show_progress=False)

        model_refresh_button.click(fn=update_model_drop,inputs=[],outputs=[modelDrop])
        simple_run_button.click(fn=model.set_model_and_generate_image,
                         inputs=[deviceDrop, modelDrop, seed, psi],
                         outputs=[result, outputSeed])
        style_run_button.click(fn=model.set_model_and_generate_styles,
                         inputs=[deviceDrop, modelDrop, seed1, seed2, seed3, psi_style, styleDrop[0], styleDrop2[0], style_interp, style_interp2],
                         outputs=[seed1im, seed2im, seed3im, styleim, seed1txt, seed2txt, seed3txt])
        random_seeds_button.click(fn=random_seeds, inputs=[seed1,seed2,seed3], outputs=[seed1,seed2,seed3])
        send_to_style_button1.click(fn=copy_seed, inputs=[outputSeed],outputs=[seed1])
        send_to_style_button2.click(fn=copy_seed, inputs=[outputSeed],outputs=[seed2])
        reuse_seed.click(fn=copy_seed,show_progress=False,inputs=[outputSeed],outputs=[seed])

        return [(ui_component, "GAN Generator", "gan_generator_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
