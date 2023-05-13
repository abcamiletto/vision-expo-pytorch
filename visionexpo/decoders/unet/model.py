import torch
from torch import nn

from ...base import upsamplers as up
from .parts import UpBlock

DEFAULT_CHANNELS = (256, 128, 64, 32, 16)


class UNetDecoder(nn.Module):
    def __init__(
        self,
        input_channels: list[int],
        input_reductions: list[int],
        decoder_channels: list[int] = None,
        upsample_layer: nn.Module = up.ConvTranspose2d,
        norm_layer: nn.Module = nn.BatchNorm2d,
        activation: nn.Module = nn.ReLU(inplace=True),
        extra_layer: nn.Module = nn.Identity(),
    ):
        super().__init__()

        if decoder_channels is None:
            decoder_channels = DEFAULT_CHANNELS[: len(input_channels) - 1]

        in_ch, skip_ch, out_ch = self.format_channels(input_channels, decoder_channels)
        up_lays = self.format_upsample_layers(input_reductions, upsample_layer)

        specs = norm_layer, activation, extra_layer
        blocks = []
        for ic, sc, oc in zip(in_ch, skip_ch, out_ch):
            upblock = UpBlock(ic, sc, oc, up_lays, *specs)
            blocks.append(upblock)

        self.blocks = nn.ModuleList(blocks)

    def forward(self, *features: torch.Tensor) -> torch.Tensor:
        # Dropping the first channel since we don't use the input image
        features = features[1:]

        # Reversing the input channels since we're going from the bottom up
        features = features[::-1]

        skips = features[1:]
        x = features[0]

        for i, decoder_block in enumerate(self.blocks):
            skip = skips[i] if i < len(skips) else None
            x = decoder_block(x, skip)

        return x

    def format_channels(self, input_channels, decoder_channels):
        # We drop the first channel since we don't use the input image
        input_channels = input_channels[1:]

        # We reverse the input channels since we're going from the bottom up
        input_channels = input_channels[::-1]

        # On the last layer we don't have a skip connection
        skip_channels = input_channels[1:] + [0]

        # The first layer has the same number of channels as the input
        # The rest has the output channels of the previous layer
        in_channels = [input_channels[0]] + list(decoder_channels[:-1])

        return in_channels, skip_channels, decoder_channels

    def format_upsample_layers(self, input_reductions, upsample_layer):
        # We drop the first reduction since we don't use the input image
        input_reductions = input_reductions[1:]

        # We reverse the input reductions since we're going from the bottom up
        input_reductions = input_reductions[::-1]

        # We build a mask to filter out the layers that don't need upsampling
        upsample_mask = []
        for i in range(1, len(input_reductions)):
            reduction = input_reductions[i]
            prev_reduction = input_reductions[i - 1]
            upsample_mask.append(reduction > prev_reduction)

        upsample_layers = []
        for boolean in upsample_mask:
            layer = upsample_layer if boolean else up.Identity()
            upsample_layers.append(layer)

        return upsample_layers
