"""Neural network for MALA."""
from abc import abstractmethod
import numpy as np 
import torch
import torch.nn as nn
import torch.nn.functional as functional

from mala.common.parameters import Parameters
try:
    import horovod.torch as hvd
except ModuleNotFoundError:
    # Warning is thrown by parameters class
    pass


class BaseNetwork(nn.Module):
    """Central network class for this framework, based on pytorch.nn.Module.

    Parameters
    ----------
    params : mala.common.parametes.Parameters
        Parameters used to create this neural network.
    """

    def __init__(self, params):
        # copy the network params from the input parameter object
        self.use_horovod = params.use_horovod
        self.mini_batch_size = params.running.mini_batch_size
        self.params = params.network

        # if the user has planted a seed (for comparibility purposes) we
        # should use it.
        if params.manual_seed is not None:
            torch.manual_seed(params.manual_seed)
            torch.cuda.manual_seed(params.manual_seed)

        # initialize the parent class
        super(BaseNetwork, self).__init__()

        # Mappings for parsing of the activation layers.
        self.activation_mappings = {
            "Sigmoid": nn.Sigmoid,
            "ReLU": nn.ReLU,
            "LeakyReLU": nn.LeakyReLU,
            "Tanh": nn.Tanh
        }

        # initialize the layers
        self.number_of_layers = len(self.params.layer_sizes) - 1

        # initialize the loss function
        if self.params.loss_function_type == "mse":
            self.loss_func = functional.mse_loss
        else:
            raise Exception("Unsupported loss function.")

        # Once everything is done, we can move the Network on the target
        # device.
        if params.use_gpu:
            self.to('cuda')

    @abstractmethod
    def forward(self, inputs):
        """Abstract method. To be implemented by the derived class."""
        pass

    def do_prediction(self, array):
        """
        Predict the output values for an input array..

        Interface to do predictions. The data put in here is assumed to be a
        scaled torch.Tensor and in the right units. Be aware that this will
        pass the entire array through the network, which might be very
        demanding in terms of RAM.

        Parameters
        ----------
        array : torch.Tensor
            Input array for which the prediction is to be performed.

        Returns
        -------
        predicted_array : torch.Tensor
            Predicted outputs of array.

        """
        self.eval()
        with torch.no_grad():
            return self(array)

    def calculate_loss(self, output, target):
        """
        Calculate the loss for a predicted output and target.

        Parameters
        ----------
        output : torch.Tensor
            Predicted output.

        target : torch.Tensor.
            Actual output.

        Returns
        -------
        loss_val : float
            Loss value for output and target.

        """
        return self.loss_func(output, target)

    # FIXME: This guarentees downwards compatibility, but it is ugly.
    #  Rather enforce the right package versions in the repo.
    def save_network(self, path_to_file):
        """
        Save the network.

        This function serves as an interfaces to pytorchs own saving
        functionalities AND possibly own saving needs.

        Parameters
        ----------
        path_to_file : string
            Path to the file in which the network should be saved.
        """
        # If we use horovod, only save the network on root.
        if self.use_horovod:
            if hvd.rank() != 0:
                return
        torch.save(self.state_dict(), path_to_file,
                   _use_new_zipfile_serialization=False)

    @classmethod
    def load_from_file(cls, params, path_to_file):
        """
        Load a network from a file.

        Parameters
        ----------
        params : mala.common.parameters.Parameters
            Parameters object with which the network should be created.
            Has to be compatible to the network architecture. This is usually
            enforced by using the same Parameters object (and saving/loading
            it to)

        path_to_file : string
            Path to the file from which the network should be loaded.

        Returns
        -------
        loaded_network : Network
            The network that was loaded from the file.
        """
        loaded_network = Network(params)
        loaded_network.load_state_dict(torch.load(path_to_file))
        loaded_network.eval()
        return loaded_network

class FeedForwardNet(BaseNetwork):
    """Initialize this network as a feed-forward network."""
        
        # Check if multiple types of activations were selected or only one
        # was passed to be used in the entire network.#
        # If multiple layers have been passed, their size needs to be correct.

    def __init__(self, params):
        super(FeedForwardNet, self).__init__(params)

        self.layers = nn.ModuleList()

        if len(self.params.layer_activations) == 1:
            self.params.layer_activations *= self.number_of_layers

        if len(self.params.layer_activations) < self.number_of_layers:
            raise Exception("Not enough activation layers provided.")
        elif len(self.params.layer_activations) > self.number_of_layers:
            raise Exception("Too many activation layers provided.")

        # Add the layers.
        # As this is a feedforward layer we always add linear layers, and then
        # an activation function
        for i in range(0, self.number_of_layers):
            self.layers.append((nn.Linear(self.params.layer_sizes[i],
                                          self.params.layer_sizes[i + 1])))
            try:
                self.layers.append(self.activation_mappings[self.params.
                                       layer_activations[i]]())
            except KeyError:
                raise Exception("Invalid activation type seleceted.")

    def forward(self, inputs):
        """
        Perform a forward pass through the network.

        Parameters
        ----------
        inputs : torch.Tensor
            Input array for which the forward pass is to be performed.

        Returns
        -------
        predicted_array : torch.Tensor
            Predicted outputs of array.
        """
        # Forward propagate data.
        for layer in self.layers:
            inputs = layer(inputs)
        return inputs

class LSTM(BaseNetwork):
    """Initialize this network as a LSTM network."""
        
    # was passed to be used in the entire network.
    def __init__(self, params):
        super(LSTM, self).__init__(params)

        self.hidden_dim = self.params.layer_sizes[-1]
        self.hidden = self.init_hidden()# check for size for validate and train

        print("initialising LSTM network")

        # First Layer
        self.first_layer = nn.Linear(self.params.layer_sizes[0], self.params.layer_sizes[1])

        # size of lstm based on bidirectional or not: 
        # https://en.wikipedia.org/wiki/Bidirectional_recurrent_neural_networks
        if (self.params.bidirection):
            self.lstm_gru_layer = nn.LSTM(self.params.layer_sizes[1], 
                                        int(self.hidden_dim / 2), 
                                        self.params.num_hidden_layers, 
                                        batch_first=True, 
                                        bidirectional=True)
        else:
            
            self.lstm_gru_layer = nn.LSTM(self.params.layer_sizes[1],
                                        self.hidden_dim, 
                                        self.params.num_hidden_layers, 
                                        batch_first=True)
        self.activation = self.activation_mappings[self.params.layer_activations[0]]()

    # Apply Network
    def forward(self, x):
        """
        Perform a forward pass through the network.

        Parameters
        ----------
        inputs : torch.Tensor
            Input array for which the forward pass is to be performed.

        Returns
        -------
        predicted_array : torch.Tensor
            Predicted outputs of array.
        """
        self.batch_size = x.shape[0]

        if (self.params.no_hidden_state):
            self.hidden = (self.hidden[0].fill_(0.0), self.hidden[1].fill_(0.0))
        
        
        self.hidden = (self.hidden[0].detach(), self.hidden[1].detach())
    
        x = self.activation(self.first_layer(x))

        if (self.params.bidirection):
            x, self.hidden = self.lstm_gru_layer(x.view(self.batch_size, 
                                                self.params.num_hidden_layers, 
                                                self.params.layer_sizes[1]), 
                                            self.hidden)
        else:
            x, self.hidden = self.lstm_gru_layer(x.view(self.batch_size, 
                                                self.params.num_hidden_layers, 
                                                self.params.layer_sizes[1]), 
                                            self.hidden)

        x = x[:, -1, :]
        x = self.activation(x)

        return (x)

    # Initialize hidden and cell states
    def init_hidden(self):
        """
        Initialize hidden state and cell state to zero when called and assigns specific sizes.

        Returns
        -------
        Hidden state and cell state : torch.Tensor
            initialised to zeros.
        """
        if (self.params.bidirection):
            h0 = torch.empty(self.params.num_hidden_layers * 2, 
                             self.mini_batch_size, 
                             self.hidden_dim // 2)
            c0 = torch.empty(self.params.num_hidden_layers * 2, 
                             self.mini_batch_size, 
                             self.hidden_dim // 2)
        else:
            h0 = torch.empty(self.params.num_hidden_layers, 
                             self.mini_batch_size, 
                             self.hidden_dim)
            c0 = torch.empty(self.params.num_hidden_layers, 
                             self.mini_batch_size, 
                             self.hidden_dim)       
        h0.zero_()
        c0.zero_()

        return (h0, c0)

class GRU(LSTM):
    """Initialize this network as a GRU network."""
        
    # was passed to be used similar to LSTM but with small tweek for the layer as GRU.
    def __init__(self, params):
        BaseNetwork.__init__(self, params)

        self.hidden_dim = self.params.layer_sizes[1]
        self.hidden = self.init_hidden()# check for size for validate and train

        # First Layer
        self.first_layer = nn.Linear(self.params.layer_sizes[0], self.params.layer_sizes[1])

        # Similar to LSTM class replaced with nn.GRU
        if (self.params.bidirection):
            self.lstm_gru_layer = nn.GRU(self.params.layer_sizes[1], 
                                        int(self.hidden_dim / 2), 
                                        self.params.num_hidden_layers, 
                                        batch_first=True, 
                                        bidirectional=True)
        else:
            
            self.lstm_gru_layer = nn.GRU(self.params.layer_sizes[1],
                                        self.hidden_dim, 
                                        self.params.num_hidden_layers, 
                                        batch_first=True)
        self.activation = self.activation_mappings[self.params.layer_activations[0]]()

    def forward(self, x):
        """Perform a forward pass through the network."""
        return super().forward(x)

       # Initialize hidden states
    def init_hidden(self):
        """
        Initialize hidden state to zero when called and assigns specific sizes.

        Returns
        -------
        Hidden state : torch.Tensor
            initialised to zeros.
        """
        print("init_hidden is called")

        if (self.params.bidirection):
            h0 = torch.empty(self.params.num_hidden_layers * 2, 
                             self.mini_batch_size, 
                             self.hidden_dim // 2)
        else:
            h0 = torch.empty(self.params.num_hidden_layers, 
                             self.mini_batch_size, 
                             self.hidden_dim)    
        h0.zero_()

        return h0
        
class TransformerNet(BaseNetwork):
    """Initialize this network as the transformer net.

    Parameters
    ----------
    params : mala.common.parametes.Parameters
        Parameters used to create this neural network. 
    """

    def __init__(self, params):
        super(TransformerNet, self).__init__(params)
    #    why is d_model==d_hidden?   
#        self.num_hidden = 91
#        self.num_tokens = 400

        self.src_mask = None
        self.pos_encoder = PositionalEncoding(self.params.layer_sizes[0], self.params.dropout)

        encoder_layers = nn.TransformerEncoderLayer(self.params.layer_sizes[0], self.params.num_heads, self.params.layer_sizes[1], self.params.dropout)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layers, self.params.num_hidden_layers)
    #   why is he not using embedding? because we already have every thing in numbers and do not need embeding?
    #   self.encoder = nn.Embedding(self.num_tokens, self.params.layer_sizes[0])

        self.decoder = nn.Linear(self.params.layer_sizes[0], self.params.layer_sizes[-1])

        self.init_weights()
        
    def generate_square_subsequent_mask(self, size):
        """
        Generate a mask so that only the current and previous tokens are visible to the transformer.

        Parameters
        ----------
        size: int
            size of the mask
        """
        mask = (torch.triu(torch.ones(size, size)) == 1).transpose(0, 1)
        mask = mask.float().masked_fill(mask == 0, float('-inf')).masked_fill(mask == 1, float(0.0))

        return mask

    def init_weights(self):
        """Initialise weights with a uniform random distribution in the range (-initrange, initrange).""" 
        initrange = 0.1
    #        self.encoder.weight.data.uniform_(-initrange, initrange)
        self.decoder.bias.data.zero_()
        self.decoder.weight.data.uniform_(-initrange, initrange)


    def forward(self, x):
        """Perform a forward pass through the network."""
        if self.src_mask is None or self.src_mask.size(0) != x.size(0):
            device = x.device
            mask = self.generate_square_subsequent_mask(x.size(0)).to(device)
            self.src_mask = mask

    #        x = self.encoder(x) * math.sqrt(self.params.layer_sizes[0])
        x = self.pos_encoder(x)
        output = self.transformer_encoder(x, self.src_mask)
        output = self.decoder(output)

        return output

class PositionalEncoding(nn.Module):
    """Injects some information of relative/absolute position of token in a sequence.
    
    Parameters
    ----------
    d_model : int
        input dimension of the model

    dropout : float
        dropout rate

    max_len: int    
        maximum length of the input sequence
    """

    def __init__(self, d_model, dropout=0.1, max_len=400):
        super(PositionalEncoding, self).__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        
        # Need to develop better form here.
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-np.log(10000.0) / d_model))
        div_term2 = torch.exp(torch.arange(0, d_model - 1 , 2).float() * (-np.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term2)
        
        pe = pe.unsqueeze(0).transpose(0, 1)
        self.register_buffer('pe', pe)

    def forward(self, x):
        """Perform a forward pass through the network."""
        x = x + self.pe[:x.size(0), :]
        return self.dropout(x)


def Network(params:Parameters):
    """
    Assign a model to an appropriate network class based on nn_type.

    Parameter:
    ---------
    params : mala.common.parametes.Parameters
    Parameters used to create this neural network.   
    """
    model: BaseNetwork= None 
    if params.network.nn_type == "feed-forward":
        model= FeedForwardNet(params)
    
    elif params.network.nn_type == "transformer":
        model= TransformerNet(params)
    
    elif params.network.nn_type == "lstm":
        model= LSTM(params)

    elif params.network.nn_type == "gru":
        model= GRU(params)
    
    
    if model is not None:
        return model
    else:
        raise Exception("Unsupported network architecture.")