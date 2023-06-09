import omni.ext
import omni.ui as ui
import requests
from PIL import Image, PngImagePlugin
import io
import base64
import os
import asyncio
import datetime
from pathlib import Path
import carb
import omni.kit.app
import omni.renderer_capture
from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file, post_viewport_message
from . import multicn

cwd = os.getcwd()

DEFAULT_NEGATIVE_PROMPT = '(worst quality:2), (low quality:2), (normal quality:2), lowres, normal quality, skin spots, acnes, skin blemishes, age spot, glans, (watermark:2),'

# https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API
# http://127.0.0.1:7860/docs

# UI doc: https://docs.omniverse.nvidia.com/kit/docs/omni.kit.documentation.ui.style/1.0.3/overview.html
# stringfield: https://docs.omniverse.nvidia.com/prod_kit/prod_kit/programmer_ref/ui/widgets/stringfield.html

def make_txt2img_param(prompt, negative_prompt):
    param = {
        "enable_hr": False,
        "denoising_strength": 0,
        "firstphase_width": 0,
        "firstphase_height": 0,
        "hr_scale": 2,
        "hr_upscaler": "string",
        "hr_second_pass_steps": 0,
        "hr_resize_x": 0,
        "hr_resize_y": 0,
        "hr_sampler_name": "string",
        "hr_prompt": "",
        "hr_negative_prompt": "",
        "prompt": prompt,
        # "styles": [
        #     "string"
        # ],
        "seed": -1,
        "subseed": -1,
        "subseed_strength": 0,
        "seed_resize_from_h": -1,
        "seed_resize_from_w": -1,
        "sampler_name": "string",
        "batch_size": 1,
        "n_iter": 1,
        "steps": 50,
        "cfg_scale": 7,
        "width": 512,
        "height": 512,
        "restore_faces": False,
        "tiling": False,
        "do_not_save_samples": False,
        "do_not_save_grid": False,
        "negative_prompt": negative_prompt,
        "eta": 0,
        "s_min_uncond": 0,
        "s_churn": 0,
        "s_tmax": 0,
        "s_tmin": 0,
        "s_noise": 1,
        "override_settings": {},
        "override_settings_restore_afterwards": True,
        "script_args": [],
        "sampler_index": "Euler a",
        "script_name": "string",
        "send_images": True,
        "save_images": False,
        "alwayson_scripts": {}
    }
    return param


# Any class derived from `omni.ext.IExt` in top level module (defined in `python.modules` of `extension.toml`) will be
# instantiated when extension gets enabled and `on_startup(ext_id)` will be called. Later when extension gets disabled
# on_shutdown() is called.
class MyExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.
    def on_startup(self, ext_id):
        carb.log_warn("[omni.hello.world] MyExtension startup")

        self.app = omni.kit.app.get_app()

        directory = Path(cwd) / '_results'
        directory.mkdir(parents=True, exist_ok=True)

        self._window = ui.Window("stable diffusion", width=300, height=600)

        self.prompt_ssm = ui.SimpleStringModel()
        self.nagative_prompt_ssm = ui.SimpleStringModel()
        self.depth_image_name = None

        with self._window.frame:
            def on_txt2img():
                payload = {
                    "prompt": self.prompt_ssm.get_value_as_string(),
                    "negative_prompt": self.nagative_prompt_ssm.get_value_as_string() or DEFAULT_NEGATIVE_PROMPT,
                    "steps": 10
                }

                url = "http://127.0.0.1:7860"
                response = requests.post(url=f'{url}/sdapi/v1/txt2img', json=payload)
                r = response.json()
                carb.log_warn(response)
                if 'images' not in r:
                    return
                for i in r['images']:
                    image = Image.open(io.BytesIO(base64.b64decode(i.split(",",1)[0])))

                    if False:
                        png_payload = {
                            "image": "data:image/png;base64," + i
                        }
                        response2 = requests.post(url=f'{url}/sdapi/v1/png-info', json=png_payload)

                        pnginfo = PngImagePlugin.PngInfo()
                        pnginfo.add_text("parameters", response2.json().get("info"))
                    else:
                        pnginfo = None

                    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                    image_name = f'{cwd}/_results/{timestamp}-txt2img.png'
                    image.save(image_name, pnginfo=pnginfo)
                    carb.log_warn(f'Saved to {image_name}')

                    self.image.source_url = image_name

            def on_depth2img():
                viewport_api = get_active_viewport()
                if viewport_api is None:
                    return

                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

                async def async_dump_image():
                    # Wait until the viewport has valid resources
                    await viewport_api.wait_for_rendered_frames()

                    settings = carb.settings.get_settings()
                    settings.set("/rtx/debugView/target", "depth")

                    # display_options = settings.get("/persistent/app/viewport/displayOptions")
                    # # Note: flags are from omni/kit/ViewportTypes.h
                    # kShowFlagAxis = 1 << 1
                    # kShowFlagGrid = 1 << 6
                    # kShowFlagSelectionOutline = 1 << 7
                    # kShowFlagLight = 1 << 8
                    # display_options = (
                    #     display_options
                    #     | (kShowFlagAxis)
                    #     | (kShowFlagGrid)
                    #     | (kShowFlagSelectionOutline)
                    #     | (kShowFlagLight)
                    # )
                    # settings.set("/persistent/app/viewport/displayOptions", display_options)
                    # Make sure these are in sync from changes above

                    show_camera = settings.get("/app/viewport/show/camera")
                    show_lights = settings.get("/app/viewport/show/lights")
                    show_grid = settings.get("/app/viewport/grid/enabled")
                    show_outline = settings.get("/app/viewport/outline/enabled")

                    settings.set("/app/viewport/show/camera", False)
                    settings.set("/app/viewport/show/lights", False)
                    settings.set("/app/viewport/grid/enabled", False)
                    settings.set("/app/viewport/outline/enabled", False)

                    for i in range(4):
                        await omni.kit.app.get_app_interface().next_update_async()

                    await omni.kit.app.get_app_interface().next_update_async()

                    image_name = f'{cwd}/_results/{timestamp}-depth.png'

                    capture_viewport_to_file(viewport_api, image_name)
                    carb.log_warn(f'Saved to {image_name}')
                    # post_viewport_message(viewport_api, f'Saved to {image_name}')
                    self.depth_image_name = image_name

                    for i in range(4):
                        await omni.kit.app.get_app_interface().next_update_async()

                    settings.set("/rtx/debugView/target", "")
                    settings.set("/app/viewport/show/camera", show_camera)
                    settings.set("/app/viewport/show/lights", show_lights)
                    settings.set("/app/viewport/grid/enabled", show_grid)
                    settings.set("/app/viewport/outline/enabled", show_outline)

                    (viewport_width, viewport_height) = viewport_api.resolution

                    # prepare data for API
                    params = {
                        "prompt": self.prompt_ssm.get_value_as_string(),
                        "negative_prompt": self.nagative_prompt_ssm.get_value_as_string() or DEFAULT_NEGATIVE_PROMPT,
                        "width": viewport_width,
                        "height": viewport_height,
                        "sampler_index": "Euler a",
                        "sampler_name": "",
                        "batch_size": 1,
                        "n_iter": 1,
                        "steps": 20,
                        "cfg_scale": 7,
                        "seed": -1,
                        "subseed": -1,
                        "subseed_strength": 0,
                        "restore_faces": False,
                        "enable_hr": False,
                        "hr_scale": 1.5,
                        "hr_upscaler": "R-ESRGAN General WDN 4xV3",
                        "denoising_strength": 0.5,
                        "hr_second_pass_steps": 10,
                        "hr_resize_x": 0,
                        "hr_resize_y": 0,
                        "firstphase_width": 0,
                        "firstphase_height": 0,
                        "override_settings": {"CLIP_stop_at_last_layers": 2},
                        "override_settings_restore_afterwards": True,
                        "alwayson_scripts": {"controlnet": {"args": []}},
                    }

                    is_send_depth = True
                    if is_send_depth:
                        depth_cn_units = {
                            "mask": "",
                            "module": "none",
                            "model": "control_v11f1p_sd15_depth",
                            "weight": 1.0,
                            "resize_mode": "Scale to Fit (Inner Fit)",
                            "lowvram": True,
                            "processor_res": 512,
                            "threshold_a": 64,
                            "threshold_b": 64,
                            "guidance": 1,
                            "guidance_start": 0.0,
                            "guidance_end": 1,
                            #"control": False,
                        }
                        with open(self.depth_image_name, "rb") as depth_file:
                            depth_cn_units["input_image"] = base64.b64encode(depth_file.read()).decode()
                        params["alwayson_scripts"]["controlnet"]["args"].append(depth_cn_units)

                    # send to API
                    response = multicn.actually_send_to_api(params)

                    # if we got a successful image created, load it into the scene
                    if response:
                        image_name = f'{cwd}/_results/{timestamp}-txt2img-controlnet.png'
                        multicn.handle_api_success(response, image_name)
                        carb.log_warn(f'Saved to {image_name}')
                        self.image.source_url = image_name

                app = omni.kit.app.get_app()

                asyncio.ensure_future(async_dump_image())


            with ui.VStack():
                with omni.ui.HStack(height=0):
                    omni.ui.Label("Prompt")
                omni.ui.Spacer(height=5)

                with omni.ui.HStack(height=100):
                    self.promp = ui.StringField(model=self.prompt_ssm, multiline=False)
                omni.ui.Spacer(height=5)
    
                with omni.ui.HStack(height=0):
                    omni.ui.Label("Nagative Prompt")
                omni.ui.Spacer(height=5)

                with omni.ui.HStack(height=100):
                    self.negative_propmt = ui.StringField(model=self.nagative_prompt_ssm, multiline=False)
                omni.ui.Spacer(height=5)

                with omni.ui.HStack(height=0):
                    ui.Button("txt2img", clicked_fn=on_txt2img)
                    ui.Button("depth2img", clicked_fn=on_depth2img)
                # label = ui.Label("")
                # field.model.add_value_changed_fn(
                #     lambda m, label=label: setText(label, m.get_value_as_string()))
                # ui.Button("Reset", clicked_fn=on_reset)
                self.image = ui.Image()


    def on_shutdown(self):
        carb.log_warn("[omni.hello.world] MyExtension shutdown")
        self._window = None
