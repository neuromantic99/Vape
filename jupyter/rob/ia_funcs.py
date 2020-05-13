import numpy as np
import json
import tifffile as tf
import os
import matplotlib.pyplot as plt
import seaborn as sns
import csv
import math
import bisect
import copy
import pickle

# global plotting params
params = {'legend.fontsize': 'x-large',
          'axes.labelsize': 'x-large',
          'axes.titlesize': 'x-large',
          'xtick.labelsize': 'x-large',
          'ytick.labelsize': 'x-large'}
plt.rcParams.update(params)
sns.set()
sns.set_style('white')


def points_in_circle_np(radius, x0=0, y0=0, ):
    '''Yields the points in a circle of a defined radius and position
    
    Inputs:
        radius -- radius of circle
        x0 -- x coord of circle centre
        y0 -- y coord of circle centre
        
    Yields:
        x -- x coord of point n in circle
        y -- y coord of point n in circle
    '''
    
    x_ = np.arange(x0 - radius - 1, x0 + radius + 1, dtype=int)
    y_ = np.arange(y0 - radius - 1, y0 + radius + 1, dtype=int)
    x, y = np.where((x_[:,np.newaxis] - x0)**2 + (y_ - y0)**2 <= radius**2)
    for x, y in zip(x_[x], y_[y]):
        yield x, y

        
def staMovie(output_dir, pkl_list=False):
    '''Function to construct stimulus-triggered average (STA) movie
    Uses tifffile exclusively and takes up a lot of RAM
    Consider using STAMovieMaker without a GUI
    
    Inputs:
        output_dir -- directory to save movie to
        pkl_list -- list of pickled objects to obtain metadata for STA movie
    '''
    
    plane = 0
    exp_list = []

    for pkl_file in pkl_list:
            
        with open(pkl_file, 'rb') as f:
            ses_obj = pickle.load(f)
                
        exp_list = [ses_obj.photostim_r, ses_obj.photostim_s]

        if ses_obj.spont.n_frames > 0:
            exp_list.append(ses_obj.spont)

        if ses_obj.whisker_stim.n_frames > 0:
            exp_list.append(ses_obj.whisker_stim)

        for exp_obj in exp_list:
                
            print('\nMaking STA movie for:', exp_obj.tiff_path)

            size_y = exp_obj.frame_y
            size_x = exp_obj.frame_x
            size_z = (exp_obj.pre_frames*2) + int(exp_obj.stim_dur/exp_obj.fps)
                
            trial_stack = np.empty([0, size_z, size_y, size_x])
                
            for file in os.listdir(exp_obj.tiff_path):
                if '.tif' in file:
                    tiff_file = os.path.join(exp_obj.tiff_path, file)
                    break
                
            for t in range(exp_obj.n_trials):
                frame_start = exp_obj.stim_start_frames[plane][t]
                trial_start = frame_start - exp_obj.pre_frames
                trial_end = frame_start + exp_obj.pre_frames + int(exp_obj.stim_dur/exp_obj.fps)

                if trial_end <= exp_obj.n_frames: # for if the tiff file is incomplete (due to corrupt data)
                    trial = tf.imread(tiff_file, key=range(trial_start, trial_end))
                    trial = np.expand_dims(trial,axis=0)
                    trial_stack = np.append(trial_stack, trial, axis=0)
                        
            trial_avg = np.mean(trial_stack, axis=0)
            avg_baseline = trial_avg[: exp_obj.pre_frames, :, :]
            baseline_mean = np.mean(avg_baseline, 0)

            df_stack = trial_avg - baseline_mean                        
            dff_stack = (df_stack/baseline_mean) * 100
            dff_stack = dff_stack.astype('uint32')

            output_path = os.path.join(output_dir, file + '_plane' + str(plane) + '.tif')

            tf.imwrite(output_path, dff_stack)
            print('STA movie made for', np.shape(trial_stack)[0], 'trials:', output_path)
            
    
def cellFluTime(pkl_list):
    '''Plots the mean raw fluorescence of all curated cells
    
    Inputs:
        pkl_list -- list of pickled objects with cellular raw fluorescence traces
    '''
    
    fig, ax = plt.subplots(nrows=len(pkl_list), ncols=1, figsize=(10,3*len(pkl_list)), sharex=True)

    for i,pkl in enumerate(pkl_list):
            
            print('Measuring mean cell fluorescence for:', pkl, '              ', end='\r')
            
            with open(pkl, 'rb') as f:
                ses_obj = pickle.load(f)

            mean_f = np.concatenate((np.mean(ses_obj.photostim_r.raw[0], axis=0),
                                     np.mean(ses_obj.photostim_s.raw[0], axis=0))
                                    )
            
            if ses_obj.whisker_stim.n_frames > 0:
                mean_f = np.concatenate((mean_f, np.mean(ses_obj.whisker_stim.raw[0], axis=0)))
                                    
            if ses_obj.spont.n_frames > 0:
                mean_f = np.concatenate((mean_f, np.mean(ses_obj.spont.raw[0], axis=0)))

            count = 0

            for frames in ses_obj.frame_list:
                x = range(count,count+frames)
                if len(pkl_list) > 1:
                    ax[i].plot(x, mean_f[x]);
                    ax[i].set_title(pkl.split('/')[-1])
                    ax[i].set_ylabel('mean_raw_f')
                else:
                    ax.plot(x, mean_f[x]);
                    ax.set_title(pkl.split('/')[-1])
                    ax.set_ylabel('mean_raw_f')
                    
                count += frames

    plt.xlabel('frames')
    labels = ['ps_random', 'ps_similar', 'whisker_stim', 'spont']
    plt.legend(labels)
    
    print('\nPlotting mean cell fluorescence...')
        
        
def frameFluTime(data_folder, legend=False):
    '''Plots results from downsampleTiff function
    The grand mean of the first and last 1000 frames from all exps in order
    
    Inputs:
        data_folder -- directory containing tiff stacks
        legend -- boolean indicating whether to plot the legend
    '''
        
        
    fig, ax = plt.subplots(nrows=2, ncols=1, figsize=(15,10), sharex=True)
    labels = []

    for _, _, files in os.walk(data_folder):
        for file in files:
            file_path = os.path.join(data_folder,file)

            tiff = tf.imread(file_path)

            raw_f_drift = np.mean(tiff, axis=(1,2)) - (2**16/2)
            norm_f_drift = raw_f_drift/raw_f_drift[0]

            ax[0].plot(raw_f_drift)
            ax[1].plot(norm_f_drift)
            labels.append(file)

    plt.xlabel('experiments');
    plt.xticks(range(0,8), np.tile(np.array(['start','end']), 4));
    ax[0].set_ylabel('raw_f');
    ax[1].set_ylabel('norm_f');
    ax[1].set_ylim([0.6, 1.2]);
    
    if legend:
        plt.legend(labels);
        
        
def downsampleTiff(pkl_list, save_path):
    '''Saves the mean of the entire first and last 1000 frames of timeseries
    
    Inputs:
        pkl_list -- list of pickled objects to take metadata from
        save_path -- directory to save mean start/end frames in
    '''
        
    for pkl in pkl_list:

        print('Downsampling experiment:', pkl, '             ', end='\r')
        
        with open(pkl, 'rb') as f:
            ses_obj = pickle.load(f)
        
        exp_list = [ses_obj.photostim_r, ses_obj.photostim_s]

        if ses_obj.spont.n_frames > 0:
            exp_list.append(ses_obj.spont)

        if ses_obj.whisker_stim.n_frames > 0:
            exp_list.append(ses_obj.whisker_stim)
        
        for exp_obj in exp_list:
            
            tiff_path = exp_obj.tiff_path
            
            file_list = os.listdir(tiff_path)
            for file in file_list:
                if '.tif' in file:
                    tiff_file = os.path.join(tiff_path, file)
  
            total_frames = range(0,exp_obj.n_frames) #get the range of frames for this experiment
            start_frames = total_frames[:1000] 
            end_frames = total_frames[-1000:] 
            
            stack_start = tf.imread(tiff_file, key=start_frames)
            stack_end = tf.imread(tiff_file, key=end_frames)
            
            mean_start = np.mean(stack_start, axis=0)
            mean_end = np.mean(stack_end, axis=0)
            
            output_path = os.path.join(save_path, tiff_path.split('/')[-1])
            
            tf.imsave(output_path + '_mean_start.tif', mean_start.astype('int16'))
            tf.imsave(output_path + '_mean_end.tif', mean_end.astype('int16'))
    
    
def s2pMeanImage(s2p_path):
    '''Return mean image saved by Suite2p
    
    Inputs: 
        s2p_path -- directory with outputs from Suite2p ('save_path0')
    
    Returns:
        mean_img -- 2D uint16 array of the mean image from Suite2p
    '''
    
    os.chdir(s2p_path)
        
    ops = np.load('ops.npy', allow_pickle=True).item()
        
    mean_img = ops['meanImg']

    mean_img = np.array(mean_img, dtype='uint16')
    
    return mean_img
    
    
def s2pMasks(s2p_path, cell_ids):
    '''Return image of cell masks with pixel value corresponding to index
    
    Inputs:
        s2p_path -- directory with outputs from Suite2p ('save_path0')
        cell_ids -- indices of cells to add to the image
    
    Returns:
        mask_img -- 2D uint16 array with cell ROIs filled with cell index value
    '''
    
    os.chdir(s2p_path)

    stat = np.load('stat.npy', allow_pickle=True)
    ops = np.load('ops.npy', allow_pickle=True).item()
    iscell = np.load('iscell.npy', allow_pickle=True)           

    mask_img = np.zeros((ops['Ly'], ops['Lx']), dtype='uint16')

    for n in range(0,len(iscell)):
        if n in cell_ids:
            ypix = stat[n]['ypix']
            xpix = stat[n]['xpix']
            mask_img[ypix,xpix] = n

    return mask_img


def getTargetImage(obj):
    '''Return image of SLM targets
    
    Inputs:
        obj -- pickled object containing SLM target areas attribute
        
    Returns:
        targ_img -- 2D uint16 array with SLM target areas filled with 255
    '''
    
    targ_img = np.zeros((obj.frame_y, obj.frame_x), dtype='uint16')
    targ_areas = obj.target_areas
        
    for targ_area in targ_areas:
        for coord in targ_area:
            targ_img[coord[0], coord[1]] = 255
        
    return targ_img

    
def s2pMaskStack(pkl_list, stam_save_path, parent_folder):
    '''Saves a stack of cell mask images for different types of cells
    Also saves stimulus-triggered average images to compare to masks
    
    Inputs:
        pkl_list -- list of pickled objects to construct mask images from
        stam_save_path -- directory containing stimulus-triggered average images/movies
        parent_folder -- directory to save cell mask images to
    '''
    
    for pkl in pkl_list:
                
        print('Retrieving s2p masks for:', pkl, '             ', end='\r')
            
        with open(pkl, 'rb') as f:
            ses_obj = pickle.load(f)
        
        pr_obj = ses_obj.photostim_r
        ps_obj = ses_obj.photostim_s
        w_obj = ses_obj.whisker_stim
        
        # list of cell ids to filter s2p masks by
        cell_id_list = [list(range(1,99999)), 
                        pr_obj.cell_id[0],
                        [pr_obj.cell_id[0][i] for i,b in enumerate(pr_obj.cell_s2[0]) if b],
                        [pr_obj.cell_id[0][i] for i,b in enumerate(pr_obj.targeted_cells) if b],
                        [ps_obj.cell_id[0][i] for i,b in enumerate(ps_obj.targeted_cells) if b],
                       ]
        
        # add whisker_stim if it exists for this session
        if w_obj.n_frames > 0:
            cell_id_list.append([w_obj.cell_id[0][i] for i,b in enumerate(w_obj.sta_sig[0]) if b])
            
            for file in os.listdir(stam_save_path):
                if all(s in file for s in ['AvgImage', w_obj.tiff_path.split('/')[-1]]):
                    w_sta_img = tf.imread(os.path.join(stam_save_path, file))
                    w_sta_img = np.expand_dims(w_sta_img, axis=0)

        # empty stack to fill with images
        stack = np.empty((0, pr_obj.frame_y, pr_obj.frame_x), dtype='uint16')
        
        s2p_path = ses_obj.s2p_path
        
        # mean image from s2p
        mean_img = s2pMeanImage(s2p_path)
        mean_img = np.expand_dims(mean_img, axis=0)
        stack = np.append(stack, mean_img, axis=0)
        
        # mask images from s2p
        for cell_ids in cell_id_list:
            mask_img = s2pMasks(s2p_path, cell_ids)
            mask_img = np.expand_dims(mask_img, axis=0)
            stack = np.append(stack, mask_img, axis=0)
        
        # sta images
        for file in os.listdir(stam_save_path):
            if all(s in file for s in ['AvgImage', pr_obj.tiff_path.split('/')[-1]]):
                pr_sta_img = tf.imread(os.path.join(stam_save_path, file))
                pr_sta_img = np.expand_dims(pr_sta_img, axis=0)
            elif all(s in file for s in ['AvgImage', ps_obj.tiff_path.split('/')[-1]]):
                ps_sta_img = tf.imread(os.path.join(stam_save_path, file))
                ps_sta_img = np.expand_dims(ps_sta_img, axis=0)
        
        stack = np.append(stack, w_sta_img, axis=0)
        stack = np.append(stack, pr_sta_img, axis=0)
        stack = np.append(stack, ps_sta_img, axis=0)
        
        # target images
        pr_targ_img = getTargetImage(pr_obj)
        pr_targ_img = np.expand_dims(pr_targ_img, axis=0)
        stack = np.append(stack, pr_targ_img, axis=0)
        
        ps_targ_img = getTargetImage(ps_obj)
        ps_targ_img = np.expand_dims(ps_targ_img, axis=0)        
        stack = np.append(stack, ps_targ_img, axis=0)
        
        # stack is now: mean_img, all_rois, all_cells, s2_cells, pr_cells, ps_cells, 
        # (whisker,) pr_sta_img, ps_sta_img, pr_target_areas, ps_target_areas
        c,y,x = stack.shape
        stack.shape = 1, 1, c, y, x, 1 # dimensions in TZCYXS order
        
        x_pix = pr_obj.pix_sz_x
        y_pix = pr_obj.pix_sz_y
        
        save_path = os.path.join(parent_folder, pkl.split('/')[-1][:-4] + '_s2p_masks.tif')
        
        tf.imwrite(save_path, stack, imagej=True, resolution=(1/y_pix, 1/x_pix), photometric='minisblack')
          
            
def combineIscell(s2p_path, extra_iscell_path):
    '''Combine and save iscell.npy files from Suite2p
    
    Inputs:
        s2p_path -- directory with outputs from Suite2p ('save_path0')
        extra_iscell_path -- iscell file to be combined with Suite2p output
    '''
    
    os.chdir(s2p_path)

    iscell = np.load('iscell.npy', allow_pickle=True) 
    iscell_original = np.where(iscell[:,0])[0]
    
    iscell_extra = np.load(extra_iscell_path, allow_pickle=True)
    iscell_extra = np.where(iscell_extra[:,0])[0]

    iscell_combined = np.append(iscell_original, iscell_extra)
    unique_cells = np.unique(iscell_combined)
    
    # backup old iscell
    np.save('iscell_backup.npy', iscell)
    
    iscell[unique_cells,0] = 1
    
    # save new iscell
    np.save('iscell.npy', iscell)
    
    
def plotCellSTAs(obj, cell_ids, fig_save_path, save=False):
    '''Plot and save stimulus-triggered average calcium traces (dFF)
    
    Inputs:
        obj -- pickled object containing calcium traces and metadata
        cell_ids -- 1D array indices of cells to plot calcium traces for
        fig_save_path -- directory to save figures to
        save -- boolean whether to save the figures or not
    '''
    
    # STA calcium traces
    stas = np.array(obj.stas[0])
    
    plt.figure(figsize=(15,5));
    plt.plot(obj.time, stas[cell_ids].T);
    plt.legend(cell_ids);
    plt.title(obj.sheet_name + '_' + obj.stim_type + ' top ten largest STAs')
    plt.ylabel('dF/F (baseline-subtracted)')
    plt.xlabel('time (sec)')
    
    if save:
        plt.savefig(os.path.join(fig_save_path,
                                 obj.sheet_name + '_' + obj.stim_type + '_top_ten_traces.png'))
        plt.savefig(os.path.join(fig_save_path,
                                 obj.sheet_name + '_' + obj.stim_type + '_top_ten_traces.svg'))
        
        
def plotCellMasks(obj, top_ten_cell_ids, stam_save_path, fig_save_path, save=False):
    '''Plot and save ten selected cell masks, stimulus-triggered average
    and mean calcium images (postage stamps)
    
    Inputs:
        obj -- pickled object containing metadata to plot
        top_ten_cell_ids -- 1D array of ten cell indices to plot
        stam_save_path -- directory containing stimulus-triggered average images
        fig_save_path -- directory to save figures to
        save -- boolean whether to save the figures or not
    '''
    
    tiff_name = obj.tiff_path.split('/')[-1]
    
    for sta_image in os.listdir(stam_save_path):
        if all(s in sta_image for s in ['Image', tiff_name]):
            sta_avg_img = tf.imread(os.path.join(stam_save_path, sta_image)) 
    
    # Cell coords (y,x)
    cell_pos = np.array(obj.cell_med[0])
    top_ten_pos = cell_pos[top_ten_cell_ids]
    
    fig, ax = plt.subplots(nrows=3, ncols=10, figsize=(15,4), sharey=True)
    fig.suptitle(obj.sheet_name + '_' + obj.stim_type + ' corresponding cell raw, STA and mask images')
    
    for i, cell_med in enumerate(top_ten_pos):
        y = int(cell_med[0])
        x = int(cell_med[1])
        cell_id = top_ten_cell_ids[i]

        cell_im = obj.mean_img[0][y-20 : y+20, x-20 : x+20]
        ax[0,i].imshow(cell_im)
        ax[0,i].set_title(cell_id)
        ax[0,i].axis('off')

        mask_im = np.zeros([40,40])
        cell_x = obj.cell_x[0][cell_id]-(x-20)
        cell_y = obj.cell_y[0][cell_id]-(y-20)
        mask_im[cell_y, cell_x] = 255
        ax[1,i].imshow(mask_im)
        ax[1,i].axis('off')
        
        sta_cell = sta_avg_img[y-20 : y+20, x-20 : x+20]
        ax[2,i].imshow(sta_cell, vmin=0, vmax=25)
        ax[2,i].axis('off')
        
        if save:
            plt.savefig(os.path.join(fig_save_path,
                                 obj.sheet_name + '_' + obj.stim_type + '_top_ten_cells.png'))
            plt.savefig(os.path.join(fig_save_path,
                                 obj.sheet_name + '_' + obj.stim_type + '_top_ten_cells.svg'))
            
            
def plotCellPositions(obj, cell_ids, fig_save_path, save=False):
    '''Plot and save positions of cells in image coordinate system
    
    Inputs:
        obj -- pickled object containing metadata to plot
        cell_ids -- 1D int array of cell indices to plot
        fig_save_path -- directory to save figures to
        save -- boolean whether to save the figures or not
    '''
    
    # Cell coords (y,x)
    cell_pos = np.array(obj.cell_med[0])
    pos = cell_pos[cell_ids]
    
    # plot colours
    stims = np.array(['pr', 'ps', 'w', 'none'])
    colours = np.array(['C0', 'C1', 'C3', 'C2'])
    
    plt.figure();
    plt.scatter(pos[:,1], pos[:,0], color=colours[np.where(stims==obj.stim_type)])
    plt.axis([0, obj.frame_x, 0, obj.frame_y])
    plt.ylabel('y_coords (pixels)')
    plt.xlabel('x_coords (pixels)')
    plt.title(obj.sheet_name + '_' + obj.stim_type + ' top ten cell positions')
    ax = plt.gca()
    ax.set_aspect('equal')
    ax.invert_yaxis()
    
    if save:
        plt.savefig(os.path.join(fig_save_path,
                                 obj.sheet_name + '_' + obj.stim_type + '_top_ten_positions.png'))
        plt.savefig(os.path.join(fig_save_path,
                                 obj.sheet_name + '_' + obj.stim_type + '_top_ten_positions.svg'))
        
        
def topTenCells(values, cell_ids):
    '''Return top ten cells based on values
    
    Inputs:
        values -- 1D float array of values to choose top ten from
        cell_ids -- 1D int array of cell indices to consider
        
    Returns:
        top_ten_cell_ids -- 1D int array of cell indexes
    '''
    
    # Sort new filtered array
    sorted_amps_ids = np.argsort(values)

    # Final ten cell indices
    top_ten_amp_ids = sorted_amps_ids[-10:]
    top_ten_cell_ids = cell_ids[top_ten_amp_ids]
    
    return top_ten_cell_ids


def plotResponseFreqTrial(obj, trial_bool, cells_bool, ax):
    '''Plot the percentage of cells responding on each trial
    
    Inputs:
        obj -- pickled object containing metadata
        trial_bool -- 2D boolean array whether cell responded on trial [cell x trial]
        cells_bool -- 1D boolean array of cells of interest
        ax -- axis object on which to plot
    '''
    trial_bool = trial_bool[cells_bool, :]
    
    trial_responses = np.sum(trial_bool, axis=0)/trial_bool.shape[0] * 100
    trial_bins = np.arange(trial_responses.shape[0]);
    
    stims = np.array(['pr', 'ps', 'w', 'none'])
    colours = np.array(['C0', 'C1', 'C3', 'C2'])
    stim_colour = colours[np.where(stims==obj.stim_type)]
    
    ax.hist(trial_bins, weights=trial_responses, bins=trial_bins,
                 align='left', histtype='step',
                 alpha=0.6, lw=2, color=stim_colour, label=obj.stim_type);
    ax.set_xlabel('trial #')
    ax.set_ylabel('% cells responding')
    ax.set_title(obj.sheet_name + ' cell responses over time')
    ax.legend()

    
def plotResponseFreqCell(obj, trial_bool, cells_bool, ax):
    '''Plot the percentage of trials each cell showed a response
    
    Inputs:
        obj -- pickled object containing metadata
        trial_bool -- 2D boolean array whether cell responded on trial [cell x trial]
        cells_bool -- 1D boolean array of cells of interest
        ax -- axis object on which to plot
    '''
    trial_bool = trial_bool[cells_bool, :]
    
    cell_responses = np.sum(trial_bool, axis=1)/trial_bool.shape[1] * 100
    cell_bins = np.arange(cell_responses.shape[0]);
    
    stims = np.array(['pr', 'ps', 'w', 'none'])
    colours = np.array(['C0', 'C1', 'C3', 'C2'])
    stim_colour = colours[np.where(stims==obj.stim_type)]
    
    ax.hist(cell_bins, weights=cell_responses, bins=cell_bins,
                 align='left', histtype='step',
                 alpha=0.6, color=stim_colour, label=obj.stim_type);
    ax.set_xlabel('cell #');
    ax.set_ylabel('% trials with responses');
    ax.set_title(obj.sheet_name + ' trial responses per cell');
        
    if any(s in obj.stim_type for s in ['pr', 'ps']):
        targets = np.where(obj.targeted_cells[cells_bool])[0]
        val = 102 if obj.stim_type == 'pr' else 105
        ax.scatter(targets, np.repeat(val, targets.shape),
                   s=10, color=stim_colour, label=obj.stim_type + ' target')
        
    ax.legend()
    

def plotCellResponseRaster(obj, trial_bool, cells_bool, ax):
    '''Plot a raster of trial responses [trial x cell]
    
    Inputs:
        obj -- pickled object containing metadata
        trial_bool -- 2D boolean array whether cell responded on trial [cell x trial]
        cells_bool -- 1D boolean array of cells of interest
        ax -- axis object on which to plot [2 x 2]
    '''
    trial_bool = trial_bool[cells_bool, :]
    cell_raster = np.where(trial_bool)

    trial_responses = np.sum(trial_bool, axis=0)/trial_bool.shape[0] * 100
    trial_bins = np.arange(trial_responses.shape[0]);

    cell_responses =  np.sum(trial_bool, axis=1)/trial_bool.shape[1] * 100
    cell_bins = np.arange(cell_responses.shape[0]);
    
    stims = np.array(['pr', 'ps', 'w', 'none'])
    colours = np.array(['C0', 'C1', 'C3', 'C2'])
    stim_colour = colours[np.where(stims==obj.stim_type)]
    
    ax[0,0].hist(trial_bins, weights=trial_responses, bins=trial_bins,
                 align='left', histtype='step', orientation='vertical',
                 alpha=0.6, lw=3, color=stim_colour, label=obj.stim_type);
    ax[0,0].set_ylabel('% cells responding');
    ax[0,0].set_title('Cell responses over time');
    ax[0,0].legend();
    
    ax[0,1].set_frame_on(False);

    ax[1,0].scatter(cell_raster[1], cell_raster[0], 
                    s=15, alpha=0.8, color=stim_colour, label=obj.stim_type);
    ax[1,0].set_ylabel('cell #');
    ax[1,0].set_xlabel('trial #');
    ax[1,0].set_title(obj.sheet_name + ' raster of single trial responses');

    ax[1,1].hist(cell_bins, weights=cell_responses, bins=cell_bins, 
                 align='left', histtype='step', orientation='horizontal',
                 alpha=0.6, color=stim_colour, label=obj.stim_type);
    ax[1,1].set_xlabel('% trials responded on');
    ax[1,1].yaxis.set_label_position("right");
    ax[1,1].set_ylabel('Trial responses per cell', rotation=270);
    
    if any(s in obj.stim_type for s in ['pr', 'ps']):
        targets = np.where(obj.targeted_cells[cells_bool])[0]
        val = 102 if obj.stim_type == 'pr' else 105
        ax[1,1].scatter(np.repeat(val, targets.shape), targets,
                   s=10, color=stim_colour, label=obj.stim_type + ' target')
    ax[1,1].legend(loc='upper center')
    

def responseFreqTrial(trial_bool, cells_bool):
    '''Plot the percentage of cells responding on each trial
    
    Inputs:
        trial_bool -- 2D boolean array whether cell responded on trial [cell x trial]
        cells_bool -- 1D boolean array of cells of interest
    '''
    trial_bool = trial_bool[cells_bool, :]
    
    trial_responses = np.sum(trial_bool, axis=0)/trial_bool.shape[0] * 100
    trial_bins = np.arange(trial_responses.shape[0]);
    
    return trial_responses