import os
import io
import ast
from typing import Union
import gradio as gr
import torch
from PIL import Image

from modules import script_callbacks, shared, ui, ui_components, images
from modules.ui_components import ToolButton

from lib_gan_extension import global_state, file_utils
from lib_gan_extension.gan_generator import GanGenerator
from lib_gan_extension.global_state import log

ui.swap_symbol = "\U00002194"  # ↔️
ui.lucky_symbol = "\U0001F340"  # 🍀
ui.folder_symbol = "\U0001F4C1"  # 📁


model = GanGenerator()

DESCRIPTION = '''# StyleGAN Image Generator

Use this tool to generate random images with a pretrained StyleGAN3 network of your choice. 
Download model pickle files and place them in sd-webui-gan-generator/models folder. 
Supports generation with the cpu or gpu0. See available pretrained networks via [https://github.com/NVlabs/stylegan3](https://github.com/NVlabs/stylegan3).
Recommend using stylegan3-r-ffhq or stylegan2-celebahq
'''


def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False, css='style.css') as ui_component:
        gr.Markdown(DESCRIPTION)
        with gr.Row():
            modelDrop = gr.Dropdown(choices = model.model_list(), value=model.default_model, label="Model Selection", info="Place into models directory", elem_id="models")
            modelDrop.input(fn=model.set_model, inputs=[modelDrop], outputs=[])

            model_refreshButton = ToolButton(value=ui.refresh_symbol, tooltip="Refresh")
            model_refreshButton.click(fn=lambda: gr.Dropdown.update(choices=model.model_list()),outputs=modelDrop)

            deviceDrop = gr.Dropdown(choices = ['cpu','cuda:0','mps'], value=model.default_device, label='Generation Device', info='Generate using CPU or GPU', elem_id="device")
            deviceDrop.input(fn=model.set_device, inputs=[deviceDrop], outputs=[])


            with gr.Group():
                with gr.Column():
                    gr.Markdown(label='Output Folder', value="Output folder", elem_id="output-folder")
                    folderButton = ToolButton(ui.folder_symbol, visible=not shared.cmd_opts.hide_ui_dir_config, tooltip="Open image output directory", elem_id="open-folder")
                    folderButton.click(
                        fn=lambda images, index: file_utils.open_folder(model.outputRoot),
                        inputs=[],
                        outputs=[],
                    )

        with gr.Tabs():
            with gr.TabItem('Simple Image Gen'):
                with gr.Row():
                    with gr.Column():
                        psiSlider = gr.Slider(-1,1,
                                        step=0.05,
                                        value=0.7,
                                        label='Truncation (psi)')
                        with gr.Row():
                            seedNum = gr.Number(label='Seed', value=-1, min_width=150, precision=0)

                            seed_randButton = ToolButton(ui.random_symbol, tooltip="Set seed to -1, which will cause a new random number to be used every time")
                            seed_randButton.click(fn=lambda: seedNum.update(value=-1), show_progress=False, inputs=[], outputs=[seedNum])

                            seed_recycleButton = ToolButton(ui.reuse_symbol, tooltip="Reuse seed from last generation")

                        simple_runButton = gr.Button('Generate Simple Image', variant="primary")

                    with gr.Column():
                        resultImg = gr.Image(label='Result', elem_id='result', sources=['upload','clipboard'], interactive=True, type="filepath")
                        resultImg.upload(
                            fn=get_params_from_image,
                            inputs=[resultImg],
                            outputs=[seedNum,psiSlider,modelDrop],
                            show_progress=False
                        )

                        seedTxt = gr.Markdown(label='Output Seed')
                        with gr.Row():
                            seed1_to_mixButton = gr.Button('Send to Seed Mixer › Left')
                            seed2_to_mixButton = gr.Button('Send to Seed Mixer › Right')

            with gr.TabItem('Seed Mixer'):
                with gr.Row():
                    mix_seed1_Num = gr.Number(label='Seed 1', value=-1, min_width=150, precision=0)

                    mix_seed1_luckyButton = ToolButton(ui.lucky_symbol, tooltip="Roll generate a new seed")
                    mix_seed1_luckyButton.click(fn=lambda: mix_seed1_Num.update(value=GanGenerator.newSeed()), show_progress=False, inputs=[], outputs=[mix_seed1_Num])

                    mix_seed1_randButton = ToolButton(ui.random_symbol, tooltip="Set seed to -1, which will cause a new random number to be used every time")
                    mix_seed1_randButton.click(fn=lambda: mix_seed1_Num.update(value=-1), show_progress=False, inputs=[], outputs=[mix_seed1_Num])

                    mix_seed1_recycleButton = ToolButton(ui.reuse_symbol, tooltip="Reuse seed from last generation")

                    mix_seed2_Num = gr.Number(label='Seed 2', value=-1, min_width=150, precision=0)

                    mix_seed2_luckyButton = ToolButton(ui.lucky_symbol, tooltip="Roll generate a new seed")
                    mix_seed2_luckyButton.click(fn=lambda: mix_seed2_Num.update(value=GanGenerator.newSeed()), show_progress=False, inputs=[], outputs=[mix_seed2_Num])

                    mix_seed2_randButton = ToolButton(ui.random_symbol, tooltip="Set seed to -1, which will cause a new random number to be used every time")
                    mix_seed2_randButton.click(fn=lambda: mix_seed2_Num.update(value=-1), show_progress=False, inputs=[], outputs=[mix_seed2_Num])

                    mix_seed2_recycleButton = ToolButton(ui.reuse_symbol, tooltip="Reuse seed from last generation")

                mix_psiSlider = gr.Slider(-1,1,
                                step=0.05,
                                value=0.7,
                                label='Truncation (psi)')  
                with gr.Row():
                    mix_interp_styleDrop = gr.Dropdown(
                        choices=["coarse (0xFF00)", "mid (0x0FF0)", "fine (0x00FF)", "total (0xFFFF)", "alt1 (0xF0F0)", "alt2 (0x0F0F)", "alt3 (0xF00F)"], label="Interpolation Mask", value="coarse (0xFF00)"
                    )
                    mix_mixSlider = gr.Slider(-1,1,
                                    step=0.01,
                                    value=1.0,
                                    label='Seed Mix (Crossfade)')

                    mix_runButton = gr.Button('Generate Style Mix', variant="primary")

                with gr.Row():
                    with gr.Column():
                        mix_seed1_Img = gr.Image(label='Seed 1 Image')
                        mix_seed1_Txt = gr.Markdown(label='Seed 1', value="")
                    with gr.Column():
                        mix_styleImg = gr.Image(label='Style Mixed Image')
                    with gr.Column():
                        mix_seed2_Img = gr.Image(label='Seed 2 Image')
                        mix_seed2_Txt = gr.Markdown(label='Seed 2', value="")

        seed_recycleButton.click(fn=copy_seed,show_progress=False,inputs=[seedTxt],outputs=[seedNum])

        simple_runButton.click(fn=model.seed_and_generate_image,
                        inputs=[seedNum, psiSlider],
                        outputs=[resultImg, seedTxt])

        seed1_to_mixButton.click(fn=copy_seed, inputs=[seedTxt],outputs=[mix_seed1_Num])
        seed2_to_mixButton.click(fn=copy_seed, inputs=[seedTxt],outputs=[mix_seed2_Num])

        mix_seed1_recycleButton.click(fn=copy_seed,show_progress=False,inputs=[mix_seed1_Txt],outputs=[mix_seed1_Num])
        mix_seed2_recycleButton.click(fn=copy_seed,show_progress=False,inputs=[mix_seed2_Txt],outputs=[mix_seed2_Num])

        mix_runButton.click(fn=model.seed_and_generate_mix,
                        inputs=[mix_seed1_Num, mix_seed2_Num, mix_psiSlider, mix_interp_styleDrop, mix_mixSlider],
                        outputs=[mix_seed1_Img, mix_seed2_Img, mix_styleImg, mix_seed1_Txt, mix_seed2_Txt])

        return [(ui_component, "GAN Generator", "gan_generator_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)

def on_ui_settings():
    global_state.init()
    section = ('gan_generator', 'StyleGAN Image Generator')
    shared.opts.add_option('gan_generator_image_format',
        shared.OptionInfo("jpg", "File format for image outputs", gr.Dropdown, {"choices": ["jpg", "png"]}, section=section))
    shared.opts.onchange('gan_generator_image_format', update_image_format)
    
script_callbacks.on_ui_settings(on_ui_settings)

def copy_seed(seedTxt) -> Union[int, None]:
    return str_utils.str2num(seedTxt)

def update_image_format():
    global_state.image_format = shared.opts.data.get('gan_generator_image_format', 'jpg')
    log(f"output format: {global_state.image_format}")

def get_params_from_image(img):
    img = Image.open(img)
    seed,psi,model_name = -1, 0.7, model.default_model()
    p = img.info
    log(f"image info: {repr(p)}")    
    if "gan-generator" in str(p):        
        # some weird stuff here for for legacy images with bad metadata
        if isinstance( p.get('parameters'), str ):
            p['parameters'] = ast.literal_eval(p.get('parameters'))
        p = peel_parameters( p )
        log(f"loading image params: {repr(p)}")
        seed = p.get('seed',seed)
        psi = p.get('psi',psi)
        model_name = p.get('model',model_name)
        # model.generate_image(seed: int,
        
    return seed, psi, model_name

def peel_parameters(data): # recursively peel 'parameters' from nested dict
    if isinstance(data, dict):
        if 'parameters' in data:
            return peel_parameters(data['parameters'])
        return {k: peel_parameters(v) for k, v in data.items()}
    return data

# monkey patch gradio to preserve exif data in jpegs
# import gradio.processing_utils as grpu
# def encode_pil_to_bytes(pil_image, format="png"):
#     with io.BytesIO() as output_bytes:
#         if format == "png":
#             save_params["pnginfo"] = grpu.get_pil_metadata(pil_image)
#         else:
#             save_params["exif"] = pil_image.info.get('exif', None)
#         pil_image.save(output_bytes, format, **save_params)
#         return output_bytes.getvalue()

# gr.processing_utils.encode_pil_to_bytes = encode_pil_to_bytes 
# log("gan_generator: monkeypatched gradio.encode_pil_to_bytes")
