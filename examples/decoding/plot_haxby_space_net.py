"""
Decoding with SpaceNet: face vs house object recognition
=========================================================

Here is a simple example of decoding with a SpaceNet prior (i.e Graph-Net,
TV-l1, etc.), reproducing the Haxby 2001 study on a face vs house
discrimination task.

See also the SpaceNet documentation: :ref:`space_net`.
"""

##############################################################################
# Load the Haxby dataset
from nilearn.datasets import fetch_haxby
data_files = fetch_haxby()

# Load Target labels
import numpy as np
labels = np.recfromcsv(data_files.session_target[0], delimiter=" ")


# Restrict to face and house conditions
target = labels['labels']
condition_mask = np.logical_or(target == "face", target == "house")

# Split data into train and test samples, using the chunks
condition_mask_train = np.logical_and(condition_mask, labels['chunks'] <= 6)
condition_mask_test = np.logical_and(condition_mask, labels['chunks'] > 6)

# Apply this sample mask to X (fMRI data) and y (behavioral labels)
# Because the data is in one single large 4D image, we need to use
# index_img to do the split easily
from nilearn.image import index_img
func_filenames = data_files.func[0]
X_train = index_img(func_filenames, condition_mask_train)
X_test = index_img(func_filenames, condition_mask_test)
y_train = target[condition_mask_train]
y_test = target[condition_mask_test]

# Compute the mean epi to be used for the background of the plotting
from nilearn.image import mean_img
background_img = mean_img(func_filenames)

##############################################################################
# Fit SpaceNet with a Graph-Net penalty
from nilearn.decoding import SpaceNetClassifier

# Fit model on train data and predict on test data
decoder = SpaceNetClassifier(memory="nilearn_cache", penalty='graph-net')
decoder.fit(X_train, y_train)
y_pred = decoder.predict(X_test)
accuracy = (y_pred == y_test).mean() * 100.
print("Graph-net classification accuracy : %g%%" % accuracy)

# Visualization
from nilearn.plotting import plot_stat_map, show
coef_img = decoder.coef_img_
plot_stat_map(coef_img, background_img,
              title="graph-net: accuracy %g%%" % accuracy,
              cut_coords=(-34, -16), display_mode="yz")

# Save the coefficients to a nifti file
coef_img.to_filename('haxby_graph-net_weights.nii')


##############################################################################
# Now Fit SpaceNet with a TV-l1 penalty
decoder = SpaceNetClassifier(memory="nilearn_cache", penalty='tv-l1')
decoder.fit(X_train, y_train)
y_pred = decoder.predict(X_test)
accuracy = (y_pred == y_test).mean() * 100.
print("TV-l1 classification accuracy : %g%%" % accuracy)

# Visualization
coef_img = decoder.coef_img_
plot_stat_map(coef_img, background_img,
              title="tv-l1: accuracy %g%%" % accuracy,
              cut_coords=(-34, -16), display_mode="yz")

# Save the coefficients to a nifti file
coef_img.to_filename('haxby_tv-l1_weights.nii')
show()


###################################
# We can see that the TV-l1 penalty is 3 times slower to converge and
# gives the same prediction accuracy. However, it yields much
# cleaner coefficient maps

