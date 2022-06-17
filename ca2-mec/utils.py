import numpy as np
import numpy.ma as ma
import expipe
import dataloader as dl


def nancorrcoef(X, Y):
    """
    Correlate X, Y (2D arrays) while ignoring nans
    """
    X = ma.masked_array(X, mask=np.isnan(X))
    Y = ma.masked_array(Y, mask=np.isnan(Y))
    return ma.corrcoef(X.flatten(), Y.flatten())[0, 1]


def action_is_recording(action_id):
    return ("type" in project.require_action(action_id).attributes) and (
        project.require_action(action_id).attributes["type"] == "Recording"
    )


def get_entity_actions(entity):
    return [action_id for action_id in actions if action_id[:3] == entity]


def trial_identity(action):
    if type(action) == str:
        project = expipe.get_project(dl.project_path())
        action = project.require_action(action)
    for tag in action.attributes["tags"]:
        if "trial_id" in tag:
            return tag.split("_")[-1]


def action_identity(trial, actions, project):
    """
    Return the action_id that matches the trial_ids.
    """
    for action in actions:
        if trial == trial_identity(project.require_action(action)):
            return action
    return None


def trial_label(action):
    """
    Returns the trial label (number) for the action.
    """
    return int(trial_id(action)[1])


def social_label(action):
    """
    socializing can happen at either of the four corners of the box (space).
    there are four types of socializing: nobox (-1) empty (0), familiar (1) or novel (2).
    this gives a 4d-vector with four possible categories each.
    """

    def social_category(str1, str2):
        """helper function"""
        if str1 == "nobox":
            return -1
        if str2 == "e":
            return 0
        if str2 == "f":
            return 1
        if str2 == "n":
            return 2

    tags = action.attributes["tags"]
    social_types = {"s": np.zeros(4), "o": np.zeros(4)}
    for tag in tags:
        if not "corner" in tag:
            continue
        stag = tag.split("_")[1:]
        # TR, TL, BL and BR, respectively
        if stag[1] == "tr":
            social_types[stag[0]][0] = social_category(*stag[-2:])
        elif stag[1] == "tl":
            social_types[stag[0]][1] = social_category(*stag[-2:])
        elif stag[1] == "bl":
            social_types[stag[0]][2] = social_category(*stag[-2:])
        elif stag[1] == "br":
            social_types[stag[0]][3] = social_category(*stag[-2:])

    return social_types


def rotmat(theta):
    """
    Returns a 2D rotation matrix for theta degrees.
    """
    theta = np.radians(theta)
    r = np.array(((np.cos(theta), -np.sin(theta)), (np.sin(theta), np.cos(theta))))
    return r


def transform_coordinates(x, y, theta=90, **kwargs):
    """
    Transform tracking coordinates to align with physical coordinates
    For this project (CA2 MEC): rotate recorded coordinates 90 degrees,
    followed by a shift to make values positive afterwards.
    """
    # rotate x,y coordinates 90 degrees using a 2D rotation matrix transform
    coords = rotmat(theta) @ np.array([x, y])
    # shift new x-coordinates to be positive
    coords -= np.array([[-1], [0]])
    return coords


def corner_masks(x, y, margin=0.4, **kwargs):
    """
    Find corner and center of box masks.
    """
    assert (
        margin < 0.5 and margin > 0
    ), "OBS! Margin must be positive and max half the box size, i.e. 0.5 OBS!"

    # center x and y coordinates
    x = x - 0.5
    y = y - 0.5
    pos = np.array([x, y]).T

    # create cardinal basis vectors
    ex, ey = np.arange(2), np.arange(2)[::-1]

    # create corner vectors: TR, TL, BL and BR, respectively
    corners = np.array([ex + ey, -ex + ey, -ex - ey, ex - ey])

    corner_masks = np.zeros((len(x), 5), dtype=bool)
    for i, corner in enumerate(corners):
        # find which quadrant positions are in, and if they are within the
        # box margins. The intersection gives the grand mask.
        quadrant_mask = ((pos * corner) > 0).all(axis=-1)
        margin_mask = (np.abs(pos) > (np.ones(2) * (0.5 - margin))).all(axis=-1)
        corner_masks[:, i] = quadrant_mask & margin_mask

    # inverse of union over corner masks
    corner_masks[:, -1] = ~np.array(corner_masks).any(axis=-1)
    return corner_masks


def truncate_recording(arr, t, t_start=0.0, t_stop=None):
    """
    Truncate recording, in seconds.
    if t_start or t_stop is None, then don't truncate
    """
    if not isinstance(arr, np.ndarray):
        return arr
    mask = np.ones(len(arr), dtype=bool)
    mask = (t > t_start) if t_start is not None else mask
    mask = mask & (t < t_stop) if t_stop is not None else mask
    return arr[mask]

def truncate_tracking_dict(tracking_dict, t_start=0.0, t_stop=None):
    """
    Truncate tracking dict, in seconds.
    if t_start or t_stop is None, then don't truncate
    """
    t = np.copy(tracking_dict["t"])
    for key in tracking_dict:
        tracking_dict[key] = truncate_recording(tracking_dict[key], t, t_start, t_stop)
    return tracking_dict


def truncate_spikes(spike_times, t):
    """
    Truncate spikes to the same length as the recording.
    """
    scope_realtime = t[[0, -1]]
    # scope spike times
    spike_times_mask = (spike_times > scope_realtime[0]) & (
        spike_times < scope_realtime[1]
    )
    spike_times = spike_times[spike_times_mask]
    return spike_times

def persistent_units(spikes, include_trials=None):
    """
    Find all units that persist across all trials for each animal (cumulative intersection over trials)
    """
    if include_trials is None:
        # include all trials
        include_trials = list(spikes.keys())

    punits = []
    for trial in spikes:
        if trial not in include_trials:
            continue
        if not punits:
            # empty list
            punits = list(spikes[trial].keys())
            continue
        punits = list(spikes[trial].keys() & punits)
    return punits
