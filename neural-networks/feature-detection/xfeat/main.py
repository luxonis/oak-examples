import depthai as dai

from utils.arguments import initialize_argparser
from stereo import stereo_mode
from mono import mono_mode

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

model_description = dai.NNModelDescription.fromYamlFile(f"xfeat_mono.{platform}.yaml")
if model_description.model != args.model:
    model_description = dai.NNModelDescription(args.model, platform=platform)

nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))

parser = nn_archive.getConfig().model.heads[0].parser
if parser == "XFeatStereoParser":
    if args.fps_limit is None:
        args.fps_limit = 5
        print(
            f"FPS limit set to {args.fps_limit} for stereo mode on {platform}. You can change it by using the -fps flag. Feel free to increase the FPS limit if you have a powerful enough machine."
        )
    stereo_mode(device, nn_archive, visualizer, args.fps_limit)
elif parser == "XFeatMonoParser":
    if args.fps_limit is None:
        args.fps_limit = 10
        print(
            f"FPS limit set to {args.fps_limit} for mono mode on {platform}. You can change it by using the -fps flag. Feel free to increase the FPS limit if you have a powerful enough machine."
        )
    mono_mode(device, nn_archive, visualizer, args.fps_limit)
else:
    raise ValueError(f"Unknown parser: {parser}")
