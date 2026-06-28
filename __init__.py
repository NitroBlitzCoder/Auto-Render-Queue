bl_info = {
    "name": "Auto Render Queue Free",
    "author": "Codex",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "Properties > Render > Auto Queue",
    "description": "Queue multiple scene/camera renders, save output presets, pause between jobs, and monitor progress.",
    "category": "Render",
}

import json
import os
import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, StringProperty


FORMAT_ITEMS = [
    ("PNG", "PNG", "Portable Network Graphics"),
    ("JPEG", "JPEG", "JPEG image"),
    ("OPEN_EXR", "OpenEXR", "High dynamic range EXR"),
    ("FFMPEG", "FFmpeg Video", "Video output through FFmpeg"),
]

STATUS_ITEMS = [
    ("PENDING", "Pending", ""),
    ("RUNNING", "Running", ""),
    ("DONE", "Done", ""),
    ("PAUSED", "Paused", ""),
    ("FAILED", "Failed", ""),
]


def safe_scene(name):
    return bpy.data.scenes.get(name)


def safe_camera(name):
    obj = bpy.data.objects.get(name)
    return obj if obj and obj.type == "CAMERA" else None


def output_directory(path):
    if not path:
        path = "//renders"
    absolute = bpy.path.abspath(path)
    os.makedirs(absolute, exist_ok=True)
    return absolute


def queue_progress(queue):
    total = len([job for job in queue if job.enabled])
    complete = len([job for job in queue if job.enabled and job.status == "DONE"])
    return complete, total


class ARQFREE_Job(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Render Job")
    scene_name: StringProperty(name="Scene", default="")
    camera_name: StringProperty(name="Camera", default="")
    frame_start: IntProperty(name="Start", default=1, min=0)
    frame_end: IntProperty(name="End", default=1, min=0)
    output_path: StringProperty(name="Output", default="//renders", subtype="DIR_PATH")
    file_format: EnumProperty(name="Format", items=FORMAT_ITEMS, default="PNG")
    enabled: BoolProperty(name="Enabled", default=True)
    status: EnumProperty(name="Status", items=STATUS_ITEMS, default="PENDING")


class ARQFREE_UL_jobs(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=item.name, icon="RENDER_ANIMATION")
        row.label(text=item.status)


class ARQFREE_OT_add_job(bpy.types.Operator):
    bl_idname = "auto_render_queue_free.add_job"
    bl_label = "Add Job"
    bl_description = "Add the current scene and active camera to the render queue"

    def execute(self, context):
        scene = context.scene
        job = scene.arq_free_jobs.add()
        job.name = scene.name + " - " + (scene.camera.name if scene.camera else "No Camera")
        job.scene_name = scene.name
        job.camera_name = scene.camera.name if scene.camera else ""
        job.frame_start = scene.frame_start
        job.frame_end = scene.frame_end
        job.output_path = scene.arq_free_output_path
        job.file_format = scene.render.image_settings.file_format if scene.render.image_settings.file_format in {item[0] for item in FORMAT_ITEMS} else "PNG"
        scene.arq_free_job_index = len(scene.arq_free_jobs) - 1
        return {"FINISHED"}


class ARQFREE_OT_add_scene_cameras(bpy.types.Operator):
    bl_idname = "auto_render_queue_free.add_scene_cameras"
    bl_label = "Add Scene Cameras"
    bl_description = "Add one queue job for every camera in the current scene"

    def execute(self, context):
        scene = context.scene
        cameras = [obj for obj in scene.objects if obj.type == "CAMERA"]
        for camera in cameras:
            job = scene.arq_free_jobs.add()
            job.name = scene.name + " - " + camera.name
            job.scene_name = scene.name
            job.camera_name = camera.name
            job.frame_start = scene.frame_start
            job.frame_end = scene.frame_end
            job.output_path = scene.arq_free_output_path
            job.file_format = scene.render.image_settings.file_format if scene.render.image_settings.file_format in {item[0] for item in FORMAT_ITEMS} else "PNG"
        scene.arq_free_job_index = len(scene.arq_free_jobs) - 1
        self.report({"INFO"}, "Added " + str(len(cameras)) + " camera jobs.")
        return {"FINISHED"}


class ARQFREE_OT_remove_job(bpy.types.Operator):
    bl_idname = "auto_render_queue_free.remove_job"
    bl_label = "Remove Job"

    def execute(self, context):
        scene = context.scene
        index = scene.arq_free_job_index
        if 0 <= index < len(scene.arq_free_jobs):
            scene.arq_free_jobs.remove(index)
            scene.arq_free_job_index = min(index, len(scene.arq_free_jobs) - 1)
        return {"FINISHED"}


class ARQFREE_OT_clear_jobs(bpy.types.Operator):
    bl_idname = "auto_render_queue_free.clear_jobs"
    bl_label = "Clear Queue"

    def execute(self, context):
        context.scene.arq_free_jobs.clear()
        context.scene.arq_free_job_index = -1
        return {"FINISHED"}


class ARQFREE_OT_start_queue(bpy.types.Operator):
    bl_idname = "auto_render_queue_free.start_queue"
    bl_label = "Start Queue"
    bl_description = "Render enabled queue jobs in order"

    def execute(self, context):
        controller_scene = context.scene
        controller_scene.arq_free_pause_requested = False
        old_window_scene = context.window.scene if context.window else None
        rendered = 0
        for job in controller_scene.arq_free_jobs:
            if not job.enabled or job.status == "DONE":
                continue
            if controller_scene.arq_free_pause_requested:
                job.status = "PAUSED"
                break
            scene = safe_scene(job.scene_name)
            camera = safe_camera(job.camera_name)
            if not scene:
                job.status = "FAILED"
                continue
            previous = (scene.camera, scene.frame_start, scene.frame_end, scene.render.filepath, scene.render.image_settings.file_format)
            try:
                if camera:
                    scene.camera = camera
                scene.frame_start = job.frame_start
                scene.frame_end = job.frame_end
                scene.render.image_settings.file_format = job.file_format
                directory = output_directory(job.output_path)
                scene.render.filepath = os.path.join(directory, job.name.replace(" ", "_") + "_")
                if context.window:
                    context.window.scene = scene
                job.status = "RUNNING"
                bpy.ops.render.render(animation=True)
                job.status = "DONE"
                rendered += 1
            except Exception as exc:
                job.status = "FAILED"
                self.report({"ERROR"}, "Render failed for " + job.name + ": " + str(exc))
            finally:
                scene.camera, scene.frame_start, scene.frame_end, scene.render.filepath, scene.render.image_settings.file_format = previous
        if context.window and old_window_scene:
            context.window.scene = old_window_scene
        self.report({"INFO"}, "Rendered " + str(rendered) + " queue jobs.")
        return {"FINISHED"}


class ARQFREE_OT_pause_queue(bpy.types.Operator):
    bl_idname = "auto_render_queue_free.pause_queue"
    bl_label = "Pause Queue"

    def execute(self, context):
        context.scene.arq_free_pause_requested = True
        self.report({"INFO"}, "Queue will pause after the current job.")
        return {"FINISHED"}


class ARQFREE_OT_resume_queue(bpy.types.Operator):
    bl_idname = "auto_render_queue_free.resume_queue"
    bl_label = "Resume Queue"

    def execute(self, context):
        for job in context.scene.arq_free_jobs:
            if job.status == "PAUSED":
                job.status = "PENDING"
        return bpy.ops.auto_render_queue_free.start_queue()


class ARQFREE_OT_save_preset(bpy.types.Operator):
    bl_idname = "auto_render_queue_free.save_preset"
    bl_label = "Save Output Preset"

    def execute(self, context):
        scene = context.scene
        data = {
            "output_path": scene.arq_free_output_path,
            "file_format": scene.arq_free_file_format,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
        }
        name = scene.arq_free_preset_name.strip() or "Preset"
        text = bpy.data.texts.get("AutoRenderQueue_Free_" + name) or bpy.data.texts.new("AutoRenderQueue_Free_" + name)
        text.clear()
        text.write(json.dumps(data, indent=2))
        self.report({"INFO"}, "Saved output preset.")
        return {"FINISHED"}


class ARQFREE_OT_load_preset(bpy.types.Operator):
    bl_idname = "auto_render_queue_free.load_preset"
    bl_label = "Load Output Preset"

    def execute(self, context):
        scene = context.scene
        name = scene.arq_free_preset_name.strip() or "Preset"
        text = bpy.data.texts.get("AutoRenderQueue_Free_" + name)
        if not text:
            self.report({"WARNING"}, "Preset not found.")
            return {"CANCELLED"}
        data = json.loads(text.as_string())
        scene.arq_free_output_path = data.get("output_path", scene.arq_free_output_path)
        scene.arq_free_file_format = data.get("file_format", scene.arq_free_file_format)
        scene.frame_start = data.get("frame_start", scene.frame_start)
        scene.frame_end = data.get("frame_end", scene.frame_end)
        return {"FINISHED"}


class ARQFREE_PT_panel(bpy.types.Panel):
    bl_label = "Auto Render Queue Free"
    bl_idname = "ARQFREE_PT_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        done, total = queue_progress(scene.arq_free_jobs)
        layout.label(text="Progress: " + str(done) + " / " + str(total), icon="TIME")
        layout.prop(scene, "arq_free_output_path")
        layout.prop(scene, "arq_free_file_format")
        row = layout.row(align=True)
        row.operator("auto_render_queue_free.add_job", icon="ADD")
        row.operator("auto_render_queue_free.add_scene_cameras", icon="CAMERA_DATA")
        layout.template_list("ARQFREE_UL_jobs", "", scene, "arq_free_jobs", scene, "arq_free_job_index", rows=5)
        row = layout.row(align=True)
        row.operator("auto_render_queue_free.start_queue", icon="RENDER_ANIMATION")
        row.operator("auto_render_queue_free.pause_queue", icon="PAUSE")
        row.operator("auto_render_queue_free.resume_queue", icon="PLAY")
        row = layout.row(align=True)
        row.operator("auto_render_queue_free.remove_job", icon="REMOVE")
        row.operator("auto_render_queue_free.clear_jobs", icon="TRASH")
        box = layout.box()
        box.label(text="Output Presets", icon="PRESET")
        box.prop(scene, "arq_free_preset_name", text="")
        row = box.row(align=True)
        row.operator("auto_render_queue_free.save_preset", icon="FILE_TICK")
        row.operator("auto_render_queue_free.load_preset", icon="IMPORT")


classes = (
    ARQFREE_Job,
    ARQFREE_UL_jobs,
    ARQFREE_OT_add_job,
    ARQFREE_OT_add_scene_cameras,
    ARQFREE_OT_remove_job,
    ARQFREE_OT_clear_jobs,
    ARQFREE_OT_start_queue,
    ARQFREE_OT_pause_queue,
    ARQFREE_OT_resume_queue,
    ARQFREE_OT_save_preset,
    ARQFREE_OT_load_preset,
    ARQFREE_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.arq_free_jobs = CollectionProperty(type=ARQFREE_Job)
    bpy.types.Scene.arq_free_job_index = IntProperty(name="Queue Index", default=-1)
    bpy.types.Scene.arq_free_output_path = StringProperty(name="Output Folder", default="//renders", subtype="DIR_PATH")
    bpy.types.Scene.arq_free_file_format = EnumProperty(name="Format", items=FORMAT_ITEMS, default="PNG")
    bpy.types.Scene.arq_free_pause_requested = BoolProperty(name="Pause Requested", default=False)
    bpy.types.Scene.arq_free_preset_name = StringProperty(name="Preset", default="Preset")


def unregister():
    del bpy.types.Scene.arq_free_preset_name
    del bpy.types.Scene.arq_free_pause_requested
    del bpy.types.Scene.arq_free_file_format
    del bpy.types.Scene.arq_free_output_path
    del bpy.types.Scene.arq_free_job_index
    del bpy.types.Scene.arq_free_jobs
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
