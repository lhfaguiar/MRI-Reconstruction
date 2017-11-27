import sys
import os
import argparse
import nibabel as nib
import keras
import numpy as np

from utils import Subsample, Correction

from matplotlib import pyplot as plt

LOW_FREQ_PERCENT = .04

# Data paths
OASIS_DATA_DIRECTORY_PREFIX = "OAS"
OASIS_DATA_RAW_RELATIVE_PATH = "RAW"
OASIS_DATA_EXTENSION_IMG = ".img"

def get_image_paths(data_path):
    oasis_subdirs = [subdir for subdir in os.listdir(data_path) if OASIS_DATA_DIRECTORY_PREFIX in subdir]
    oasis_raw_paths = []
    for subdir in oasis_subdirs:
        raws_subdir = os.path.join(data_path, subdir, OASIS_DATA_RAW_RELATIVE_PATH)
        for raw_fname in [fname for fname in os.listdir(raws_subdir) if OASIS_DATA_EXTENSION_IMG in fname]:
            oasis_raw_paths.append(os.path.join(raws_subdir, raw_fname))

    return oasis_raw_paths

def load_image(image_path):
    img = nib.load(image_path)
    data = np.array(np.squeeze(img.get_data()), dtype=np.float32)
    data -= data.min()
    data = data / data.max()
    data = data * 255.0
    return data

def load_image(image_path, substep):
    original_img = nib.load(image_path)

    original_data = np.array(np.squeeze(original_img.get_data()) dtype=np.float32)
    original_data -= original_data.min()
    original_data = original_data / original_data.max()
    original_data = original_data * 255.0
    original_data = np.moveaxis(original_data, -1, 0).reshape(128, 256, 256, 1)

    subsampled_img, _ = Subsample.subsample(image_path, substep=substep, lowfreqPercent=LOW_FREQ_PERCENT)
    subsampled_data = np.moveaxis(subsampled_img, -2, 0)

    return subsampled_data, original_data

def load_net(net_path):
    return keras.models.load_model(net_path)

def eval_diff_plot(net_path, img_path, substep):
    test_subsampled, test_original = load_image(img_path, substep)
    fnet = load_net(net_path)

    result = fnet.predict(test_subsampled[70].reshape(1, 256, 256, 1))

    magnitude_spectrum = 20*np.log(np.abs(result.reshape(256,256)))
    plt.subplot(121),plt.imshow(test_original[70].reshape(256,256), cmap = 'gray')
    plt.title('Input Image'), plt.xticks([]), plt.yticks([])
    plt.subplot(122),plt.imshow(result.reshape(256,256), cmap = 'gray')
    plt.title('Magnitude Spectrum'), plt.xticks([]), plt.yticks([])
    plt.show()

def compute_loss(output, original):
    return np.linalg.norm(output.flatten() - original.flatten())

def eval_loss(net_path, data_path, substep):
    fnet = load_net(net_path)
    img_paths = get_image_paths(data_path)
    losses = []
    for img_path in img_paths:
        test_subsampled, test_original = load_image(img_path, substep)
        for slice_idx in range(128):
            fnet_input = test_subsampled[slice_idx].reshape(1, 256, 256, 1)
            fnet_output = fnet.predict(fnet_input)
            corrected_output = Correction.Correction(fnet_input, fnet_output, substep=substep, lowfreqPercent=LOW_FREQ_PERCENT)
            loss = compute_loss(output=corrected_output, original=test_original[slice_idx])
            losses.append(loss)

    return float(sum(losses)) / len(losses)

def main():
    parser = argparse.ArgumentParser(description='Train FNet on MRI image data')
    parser.add_argument('-i', '--img_path', type=str, help="The path to an OASIS MRI image to evaluate and diff-plot")
    parser.add_argument('-s', '--substep', type=int, default=4, help="The substep used for subsampling (4 in the paper)")
    parser.add_argument('-n', '--net_path', type=str, help="The path to a trained FNet")
    parser.add_argument('-d', '--data_path', type=str, help="The path to a test set of Analyze images to evaluate for loss computation")
    args = parser.parse_args()

    if not args.substep:
        raise Exception("--substep must be specified!")
    elif not args.net_path:
        raise Exception("--net_path must be specified!")

    if args.img_path:
        eval_diff_plot(args.net_path, args.img_path, args.substep)
    elif args.data_path:
        print("MSE: {}".format(eval_loss(args.net_path, args.data_path, args.substep)))
    else:
        raise Exception("Either '--img_path' or '--data_path' must be specified!")


if __name__ == "__main__":
    main()
