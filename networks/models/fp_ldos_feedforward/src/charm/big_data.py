# FP LDOS, Data Loaders

import os, sys
import numpy as np
import timeit
#import torch.nn as nn
#import torch.nn.functional as F

import torch

#import torch.utils.Dataset
import torch.utils.data.distributed
import torch.utils.data
import torch.utils
import horovod.torch as hvd


###-----------------------------------------------------------------------###

# Big Data Dataset for training data that does not fit into memory
class Big_Charm_Dataset(torch.utils.data.Dataset):

    def __init__(self, args, \
                 input_fpaths, \
                 output_fpaths, \
                 num_samples, \
                 input_sample_shape, \
                 output_sample_shape, \
                 input_subset=None, \
                 output_subset=None, \
                 input_scaler_kwargs={}, \
                 output_scaler_kwargs={}):
        # input:
        ## args:                    Argparser args
        ## input_fpaths:            paths to input numpy files
        ## output_fpaths:           paths to output numpy files
        ## num_samples:             number of samples per file
        ## input_sample_shape:      shape of input sample
        ## output_sample_shape:     shape of output sample
        ## input_subset:            take subset of numpy file sample to 
        ##                          fit input_sample_shape
        ## output_subset:           take subset of numpy file sample to 
        ##                          fit input_sample_shape
        ## input_scaler_kwargs:     dict of input scaler options
        ## output_scalar_kwargs:    dict of output scaler options 
       
        self.num_samples = num_samples
        self.num_files = len(input_fpaths)

#        print("Num files: %d" % self.num_files)

        if (self.num_files == 0):
            raise ValueError("\n\nNo files provided to the Big Charm Dataset. Exiting.\n\n")
        if (self.num_files != len(output_fpaths)):
            raise ValueError("\nInput file list not equal in length " + \
                             "with Output file list. Exiting.\n\n")

        



        tic = timeit.default_timer()
        self.input_scaler  = Big_Data_Scaler(input_fpaths, \
                                             num_samples, \
                                             input_sample_shape, \
                                             input_subset, \
                                             **input_scaler_kwargs)
        toc = timeit.default_timer()

        print("Input Scaler Timing: %4.4f" % (toc - tic))

        tic = timeit.default_timer()
        self.output_scaler = Big_Data_Scaler(output_fpaths, \
                                             num_samples, \
                                             output_sample_shape, \
                                             output_subset, \
                                             **output_scaler_kwargs)
        toc = timeit.default_timer()                            

        print("Output Scaler Timing: %4.4f" % (toc - tic))
       
        if (hvd.rank() == 0):
            print("Input FP Factors")
            self.input_scaler.print_factors()
            print("Output LDOS Factors")
            self.output_scaler.print_factors()

#        hvd.allreduce(torch.tensor(0), name="barrier")
#        print("\n\nDone.\n\n")
#        exit(0);   

        # List of numpy arrays to preserve mmap_mode
        self.input_datasets = [] 
        self.output_datasets = []

        # Load Datasets
        for idx, path in enumerate(input_fpaths):
            self.input_datasets.append(np.load(path, mmap_mode="r"))
        for idx, path in enumerate(output_fpaths):
            self.output_datasets.append(np.load(path, mmap_mode="r"))

        # Input subset and reshape
        for i in range(self.num_files):
            self.input_datasets[i] = np.reshape(self.input_datasets[i], \
                                                np.insert(input_sample_shape, \
                                                          0, self.num_samples))
            
            if (input_subset is not None):
                self.input_datasets[i] = self.input_datasets[i][:, input_subset]

        # Output subset and reshape 
        for i in range(self.num_files):
            self.output_datasets[i] = np.reshape(self.output_datasets[i], \
                                                 np.insert(output_sample_shape, \
                                                           0, self.num_samples))
            
            if (output_subset is not None):
                self.output_datasets[i] = self.output_datasets[i][:, output_subset]






#            self.output_datasets[i] = self.output_datasets[i][:,:,:,ldos_idxs]

#            data_shape = self.output_datasets[i].shape 

#            grid_pts = data_shape[0] * data_shape[1] * data_shape[2]

#            self.output_datasets[i] = np.reshape(self.output_datasets[i], \
#                                                [self.num_samples, output_sample_shape])
            
#            self.output_datasets[i] = self.output_datasets[i]

        # !!! Need to modify !!! 
        # Switch args.ldos_length -> args.ldos_length and args.final_ldos_length 
#        if (data_name == "test"):
#            args.ldos_length = data_shape[-1]
#            args.grid_pts = grid_pts

#        self.grid_pts = grid_pts

        # Consistency Checks


    # Fetch a sample
    def __getitem__(self, idx):
      
        file_idx = idx // self.num_samples
        sample_idx = idx % self.num_samples

        scaled_input  = self.input_scaler.do_scaling_sample(self.input_datasets[file_idx][sample_idx])
        scaled_output = self.output_scaler.do_scaling_sample(self.output_datasets[file_idx][sample_idx])

        input_tensor  = torch.tensor(scaled_input).float()
        output_tensor = torch.tensor(scaled_output).float()

        return input_tensor, output_tensor

    # Number of samples in dataset
    def __len__(self):
        return self.num_files * self.num_samples



###-----------------------------------------------------------------------###


# Compressed Dataset
#class Compressed_Dataset(torch.utils.data.Dataset):
#
#    def __init__(self, args, data_name, fp_data, ldos_data):
#
#        if (hvd.rank() == 0):
#            print("Creating Big Compressed Dataset:")
#
#        self.args = args
#        self.sample = 0
#       
#        if (args.load_encoder):
#            self.encoder = 0
#        else:
#
#            args.fp_length = fp_data.shape[1]
#
#            self.num_subdim = 2
#            self.ks = 256
#
#            if (args.fp_length % self.num_subdim != 0):
#                print("\n\nPQKMeans division error. %d not a factor of %d. Exiting!\n" % (self.num_subdim, args.fp_length))
#                exit(0)
#
#            self.pqkmeans.encoder.PQEncoder(num_subdim=self.num_subdim, Ks=self.ks
#
#            sample_pts = fp_data.shape[0] * args.compress_fit_ratio
#
#            if (hvd.rank() == 0):
#                print("Begin fitting encoder to subset of data")
#    
#            tic = timeit.default_timer()
#            self.encoder.fit(fp_data[:sample_pts])
#            toc = timeit.default_timer()
#
#            if (hvd.rank() == 0):
#                print("Fit %d samples to %s dataset encoder: %4.4fs" % (sample_pts, data_name, toc - tic))
#            
#            tic
#
#            fp_encode = encoder.transform(fp_data)
#        
#
#            self
#
#
#
#
#        self.cluster_ids = []
#
#        for i in range(args.clusters):
#            self.cluster_ids.append()
#
#       
#
#    def __getitem__(self, idx):
#
#    
#
#        return 0;
#
#    def __len__(self):
#        return 1;



###-----------------------------------------------------------------------###


###-----------------------------------------------------------------------###

class Big_Data_Scaler:

    def __init__(self, 
                 file_paths,
                 num_samples, 
                 data_shape,
                 data_subset=None,
                 element_scaling=False, 
                 standardize=False, 
                 normalize=False, 
                 max_only=False,
                 apply_log=False):

        self.file_paths         = file_paths
        self.num_samples        = num_samples
        self.data_shape         = data_shape
        self.data_subset        = data_subset

        self.element_scaling    = element_scaling
        self.standardize        = standardize
        self.normalize          = normalize
        self.max_only           = max_only
        self.apply_log          = apply_log

        self.no_scaling         = not standardize and not normalize

        print("\nCalculating scaling factors.")
        self.setup_scaling()

    
    def print_factors(self):
        if (self.no_scaling):
            print("No Scaling")

        if (self.element_scaling):
            if (self.standardize):
                print("Scaling Element Factors (Mean/Std)")
            elif (self.normalize):
                print("Scaling Element Factors (Min/Max)")
        else:
            if (self.standardize):
                print("Scaling Total Factors (Mean/Std)")
            elif (self.normalize):
                print("Scaling Total Factors (Min/Max)")

        for i in range(self.factors.shape[1]):
            print("%d: %4.4f, %4.4f" % (i, self.factors[0, i], self.factors[1, i]))


    # Scale one sample
    def do_scaling_sample(self, x):

        if (self.no_scaling):
            return x

        if (not self.element_scaling):
            if (self.normalize):
                return (x - self.factors[0, 0]) / (self.factors[1, 0] - self.factors[0, 0])
            elif(self.standardize):
                return (x - self.factors[0, 0]) / self.factors[1, 0]
            else:
                raise ValueError("\n\nBad scaling choices.\n\n")
 
        else:
            if (self.normalize):
                return (x - self.factors[0, :]) / (self.factors[1, :] - self.factors[0, :])
            elif (self.standardize):
                return (x - self.factors[0, :]) / self.factors[1, :]
                
            else:
                raise ValueError("\n\nBad scaling choices.\n\n")


    # Undo scaling of one sample
    def undo_scaling_sample(self, x):

        if (self.no_scaling):
            return x

        if (not self.element_scaling):
            if (self.normalize):
                return (x * (self.factors[1, 0] - self.factors[0, 0])) + self.factors[0, 0]
            elif(self.standardize):
                return (x * self.factors[1, 0]) + self.factors[1, 0]
            else:
                raise ValueError("\n\nBad scaling choices.\n\n")
 
        else:
            if (self.normalize):
                return (x * (self.factors[1, :] - self.factors[0, :])) + self.factors[0, :]
            elif (self.standardize):
                return (x * self.factors[1, :]) + self.factors[0, :]
                
            else:
                raise ValueError("\n\nBad scaling choices.\n\n")


    # Scale batch (or full) data
    def do_scaling_batch(self, x):

        if (self.no_scaling):
            return x

        if (not self.element_scaling):
            if (self.normalize):
                return (x - self.factors[0, 0]) / (self.factors[1, 0] - self.factors[0, 0])
            elif(self.standardize):
                return (x - self.factors[0, 0]) / self.factors[1, 0]
            else:
                raise ValueError("\n\nBad scaling choices.\n\n")
 
        else:
            if (self.normalize):
                return (x - self.factors[0, :, None]) / (self.factors[1, :, None] - self.factors[0, :, None])
            elif (self.standardize):
                return (x - self.factors[0, :, None]) / self.factors[1, :, None]
                
            else:
                raise ValueError("\n\nBad scaling choices.\n\n")


    # Undo scaling of batch (or full) data
    def undo_scaling_batch(self, x):

        if (self.no_scaling):
            return x

        if (not self.element_scaling):
            if (self.normalize):
                return (x * (self.factors[1, 0] - self.factors[0, 0])) + self.factors[0, 0]
            elif(self.standardize):
                return (x * self.factors[1, 0]) + self.factors[1, 0]
            else:
                raise ValueError("\n\nBad scaling choices.\n\n")
 
        else:
            if (self.normalize):
                return (x * (self.factors[1, :, None] - self.factors[0, :, None])) + self.factors[0, :, None]
            elif (self.standardize):
                return (x * self.factors[1, :, None]) + self.factors[0, :, None]
                
            else:
                raise ValueError("\n\nBad scaling choices.\n\n")




    # Calculate and store scaling factors
    def setup_scaling(self):

        # Factors
        # factors[0,:], Min (normalize) or Mean (standardize)
        # factors[1,:], Max (normalize) or Std  (standardize)

        if (not self.element_scaling):
            self.factors = np.zeros([2, 1])
        else:
            self.factors = np.zeros([2, self.data_subset.size])
       
        if (self.no_scaling):
            print("No scaling. Neither standardize nor normalize scaling choosen. ")
            return;

        sample_count = 0
        count_elems = 0

#        print("Setup")

        for idx, fpath in enumerate(self.file_paths):

            file_data = np.load(fpath)

            # Shape Data
            file_data = np.reshape(file_data, \
                                   np.insert(self.data_shape, \
                                             0, self.num_samples))
            # Subset Data
            if (self.data_subset is not None):
                file_data = file_data[:, self.data_subset]

            # Final data shape
            self.new_shape = np.array(file_data.shape[1:])

            # Total Scaling
            if (not self.element_scaling):
                if (self.normalize):
                    self.calc_normalize(file_data, 0)
                elif (self.standardize):
                    count_elems = file_data.size
                else:
                    raise ValueError("\n\nBad scaling choices.\n\n")

            # Element Scaling
            else:
                for elem in range(np.prod(self.new_shape)):

#                    print("Elem %d" % elem)
#                    elem_idx = np.zeros(self.new_shape, dtype=bool)
#                    elem_slice = np.array([])

                    if (file_data.ndim != 2):
                        raise ValueError("\nScaler only supports [samples x vector] data.\n")

                    if (self.normalize):
                        self.calc_normalize(file_data[:, elem], elem)
                    elif (self.standardize):
                        self.calc_standardize(file_data[:, elem], elem, sample_count)
                    else:
                        raise ValueError("\n\nBad scaling choices.\n\n")

            sample_count += self.num_samples 
        
#        if (self.standardize):
#            self.factors[1, :] = np.sqrt(self.factors[1, :] / standardize_count)

    # Calculate min/max normalization factors for data_batch
    def calc_normalize(self, data, factor_idx):
        
        # Calc data min
        if (not self.max_only):
            data_min = np.min(data)
            if (data_min < self.factors[0, factor_idx]):
                self.factors[0, factor_idx] = data_min

        # Calc data max
        data_max = np.max(data)
        if (data_max > self.factors[1, factor_idx]):
            self.factors[1, factor_idx] = data_max

    # Calculate mean/std normalization factors for data_batch
    def calc_standardize(self, data, factor_idx, count):
        

        #        print(data.size)

#        num_vals = data.size

#        data_mean = np.mean(data)
#        data_std = np.std(data)

#        count += num_vals

#        deltas = np.subtract(data, self.factors[0, factor_idx] * num_vals)
#        self.factors[0, factor_idx] += np.sum(deltas / count)

#        deltas2 = np.subtract(data, self.factors[0, factor_idx] * num_vals)
#        self.factors[1, factor_idx] += np.sum(deltas * deltas2)

        new_mean = np.mean(data)
        new_std = np.std(data)

        num_new_vals = data.size

        old_mean = self.factors[0, factor_idx]
        old_std = self.factors[1, factor_idx]

        self.factors[0, factor_idx] = \
            count / (count + num_new_vals) * old_mean + \
            num_new_vals / (count + num_new_vals) * new_mean

        self.factors[1, factor_idx] = \
            count / (count + num_new_vals) * old_std ** 2 + \
            num_new_vals / (count + num_new_vals) * new_std ** 2 + \
            (count * num_new_vals) / (count + num_new_vals) * \
            (old_mean - new_mean) ** 2

        self.factors[1, factor_idx] = np.sqrt(self.factors[1, factor_idx])

#        print(self.factors[0, factor_idx])
#        print(self.factors[1, factor_idx])


###-----------------------------------------------------------------------###

# Normalize FP or LDOS
#def scale_data(args, data_name, \
#               data_train, data_validation, data_test, \
#               apply_log=False, \
#               row_scaling=False, \
#               norm_scaling=False, max_only=False, \
#               standard_scaling=False):
#
#    if (len(data_train.shape) != 2 or len(data_validation.shape) != 2 or len(data_test.shape) != 2):
#        if (hvd.rank() == 0):
#            print("\nIssue in %s data shape lengths (train, valid, test): (%d, %d, %d), expected length 2. Exiting.\n\n" \
#                % (data_name, len(data_train.shape), len(data_validation.shape), len(data_test.shape)))
#        exit(0);
#   
#    # Number of elements in each sample vector
#    data_length = data_train.shape[1]
#
#    # Apply log function to the data
#    if (apply_log):
#        if (hvd.rank() == 0):
#            print("Applying Log function to %s" % data_name)   
#
#        train_min = np.min(data_train)
#        validation_min = np.min(data_validation)
#        test_min = np.min(data_test)
#        
#        log_shift = np.array([1e-8])
#
#        train_min += log_shift
#        validation_min += log_shift
#        test_min += log_shift
#
#        if (train_min <= 0.0 or validation_min <= 0.0 or test_min <= 0.0):
#            if (hvd.rank() == 0):
#                print("\nApplying the log fn to %s fails because there are values <= 0. Exiting.\n\n" % data_name)
#            exit(0);
#
#        np.save(args.model_dir + "/%s_log_shift" % data_name, log_shift)
#
#        data_train      = np.log(data_train + log_shift)
#        data_validation = np.log(data_validation + log_shift)
#        data_test       = np.log(data_test + log_shift)
#        
#    # Row vs total scaling
#    if (row_scaling and (norm_scaling or standard_scaling)):
#        scaling_factors = np.zeros([2, data_length])
#        scaling_factors_fname = "/%s_factor_row" % data_name
#    else:
#        scaling_factors = np.zeros([2, 1])
#        scaling_factors_fname = "/%s_factor_total" % data_name
#
#    # Scale features
#    if (norm_scaling or standard_scaling):
#        # Apply data normalizations
#        for row in range(data_length):
#
#            # Row scaling
#            if (row_scaling):
#                if (standard_scaling):
#
#                    if (args.calc_training_norm_only):
#                        data_meanv = np.mean(data_train[:, row])                
#                        data_stdv  = np.std(data_train[:, row])
#                                                            
#                    else: 
#                        data_meanv = np.mean(np.concatenate((data_train[:, row], \
#                                                             data_validation[:, row], \
#                                                             data_test[:, row]), axis=0))
#                        data_stdv  = np.std(np.concatenate((data_train[:, row], \
#                                                            data_validation[:, row], \
#                                                            data_test[:, row]), axis=0))
#           
#                    data_train[:, row]      = (data_train[:, row] - data_meanv) / data_stdv
#                    data_validation[:, row] = (data_validation[:, row] - data_meanv) / data_stdv
#                    data_test[:, row]       = (data_test[:, row] - data_meanv) / data_stdv
#       
#                    scaling_factors[0, row] = data_meanv
#                    scaling_factors[1, row] = data_stdv
#
#                else:
#                    if (max_only):
#                        data_minv = 0
#                    else:
#                        if (args.calc_training_norm_only):
#                            data_minv = np.min(data_train[:, row])
#                        else:
#                            data_minv = np.min(np.concatenate((data_train[:, row], \
#                                                             data_validation[:, row], \
#                                                             data_test[:, row]), axis=0))
#                    if (args.calc_training_norm_only):
#                        data_maxv = np.max(data_train[:, row])
#                    else:
#                        data_maxv = np.max(np.concatenate((data_train[:, row], \
#                                                         data_validation[:, row], \
#                                                         data_test[:, row]), axis=0))
#
#                    if (data_maxv - data_minv < 1e-12):
#                        print("\nNormalization of %s error. max-min ~ 0. Exiting. \n\n" % data_name)
#                        exit(0);
#            
#                    data_train[:, row]      = (data_train[:, row] - data_minv) / (data_maxv - data_minv)
#                    data_validation[:, row] = (data_validation[:, row] - data_minv) / (data_maxv - data_minv)
#                    data_test[:, row]       = (data_test[:, row] - data_minv) / (data_maxv - data_minv)
#            
#            # No row scaling
#            else:
#                if (standard_scaling):
#
#                    if (args.calc_training_norm_only):
#                        data_mean = np.mean(data_train)
#                        data_std = np.std(data_train)
#
#                    else:
#                        data_mean = np.mean(np.concatenate((data_train, \
#                                                          data_validation, \
#                                                          data_test), axis=0))
#                        data_std  = np.std(np.concatenate((data_train, \
#                                                         data_validation, \
#                                                         data_test), axis=0))
#                     
#                    data_train      = (data_train - data_mean) / data_std
#                    data_validation = (data_validation - data_mean) / data_std
#                    data_test       = (data_test - data_mean) / data_std
#                
#                    scaling_factors[0, row] = data_mean
#                    scaling_factors[1, row] = data_std
#                
#                else: 
#                    if (max_only):
#                        data_min = 0
#                    else:
#                        if (args.calc_training_norm_only):
#                            data_min = np.min(data_train)
#                        else:
#                            data_min = np.min(np.concatenate((data_train, \
#                                                            data_validation, \
#                                                            data_test), axis=0))  
#                    if (args.calc_training_norm_only):
#                        data_max = np.max(data_train)
#                    else:
#                        data_max = np.max(np.concatenate((data_train, \
#                                                        data_validation, \
#                                                        data_test), axis=0))
#                        
#                    if (data_max - data_min < 1e-12):
#                        print("\nNormalization of %s error. max-min ~ 0. Exiting\n\n" % data_name)
#                        exit(0);
#
#                    data_train      = (data_train - data_min) / (data_max - data_min)
#                    data_validation = (data_validation - data_min) / (data_max - data_min)
#                    data_test       = (data_test - data_min) / (data_max - data_min)
#
#                    scaling_factors[0, row] = data_min
#                    scaling_factors[1, row] = data_max
#
#
#            if (hvd.rank() == 0):
#                if (row_scaling):
#                    if (standard_scaling):
#                        print("%s Row: %g, Mean: %g, Std: %g" % (data_name, row, scaling_factors[0, row], scaling_factors[1, row]))
#                    else:
#                        print("%s Row: %g, Min: %g, Max: %g" % (data_name, row, scaling_factors[0, row], scaling_factors[1, row]))
#                else: 
#                    if (standard_scaling):
#                        print("%s Total, Mean: %g, Std: %g" % (data_name, scaling_factors[0, 0], scaling_factors[1, 0]))
#                    else:
#                        print("%s Total, Min: %g, Max: %g" % (data_name, scaling_factors[0, 0], scaling_factors[1, 0]))
#
#            if (row == 0):
#                if (row_scaling):
#                    if (standard_scaling):
#                        scaling_factors_fname += "_standard_mean_std"
#                    else:
#                        scaling_factors_fname += "_min_max"
#
#                else: 
#                    if (standard_scaling):
#                        scaling_factors_fname += "_standard_mean_std"
#                    else:
#                        scaling_factors_fname += "_min_max"
#
#                    # No Row scaling
#                    break;
#    
#    # No LDOS scaling
#    else:  
#        if (hvd.rank() == 0):
#            print("Not applying scaling to %s." % data_name)
#        # Identity scaling
#        scaling_factors[0,0] = 0.0
#        scaling_factors[1,0] = 1.0
#        scaling_factors_fname += "_min_max"
# 
#    # Save normalization coefficients
#    np.save(args.model_dir + scaling_factors_fname, scaling_factors)
#
##    hvd.allreduce(torch.tensor(0), name='barrier')
#
#    return (data_train, data_validation, data_test)
#

###-----------------------------------------------------------------------###





