from miscnn.model.model import Model
from miscnn.neural_network.model import Neural_Network
import json
from miscnn.data_loading.data_io import create_directories
from tensorflow.keras.callbacks import ModelCheckpoint

#-----------------------------------------------------#
#            Neural Network (model) class             #
#-----------------------------------------------------#
# Class which represents the Neural Network and which run the whole pipeline
class Model_Group(Model):
    
    def __init__ (self, models, preprocessor, verify_preprocessor=True):
        Model.__init__(self, preprocessor)
        
        self.models = models
        
        for model in self.models:
            if (not isinstance(model, Model)):
                raise RuntimeError("Model Groups can only be comprised of objects inheriting from Model")
            if verify_preprocessor and not model.preprocessor == self.preprocessor:
                raise RuntimeError("not all models use the same preprocessor. This can have have unintended effects and instabilities. To disable this warning pass \"verify_preprocessor=False\"")
        
    
    def train(self, sample_list, epochs=20, iterations=None, callbacks=[]):
        tmp = self.preprocessor.data_io.output_path
        for model in self.models:
            out_dir = create_directories(tmp, "group_" + str(model.id))
            model.preprocessor.data_io.output_path = out_dir
            cb_list = []
            if (not isinstance(model, ModelGroup)):
                #this child is a leaf. ensure correct storage.
                cb_model = ModelCheckpoint(os.path.join(subdir, "model.hdf5"),
                                           monitor="val_loss", verbose=1,
                                           save_best_only=True, mode="min")
                cb_list = callbacks + [cb_model]
            else:
                cb_list = callbacks
                
            # Reset Neural Network model weights
            model.reset()
            model.train(sample_list, epochs=epochs, iterations=iterations, callbacks=cb_list)
    
    def predict(self, sample_list, aggregation_func, activation_output=False):
        tmp = self.preprocessor.data_io.output_path
        for model in self.models:
            out_dir = create_directories(tmp, "group_" + str(model.id))
            model.preprocessor.data_io.output_path = out_dir
            model.predict(sample_list, activation_output=activation_output)
        
        for sample in sample_list:
            sample = None
            prediction_list = []
            for model in self.models:
                out_dir = os.path.join(tmp, "group_" + str(model.id))
                model.preprocessor.data_io.output_path = out_dir
                s = model.preprocessor.data_io.sample_loader(sample, load_seg=False, load_pred=True)
                if sample is None:
                    sample = s.img_data
                prediction_list.append(s.pred_data)
            res = aggregation_func(sample, prediction_list)
            self.preprocessor.data_io.save_prediction(res, sample)
        
        #deal with results
    
    # Evaluate the Model using the MIScnn pipeline
    def evaluate(self, training_samples, validation_samples, evaluation_path="evaluation", epochs=20, iterations=None, callbacks=[], store=True):
        for model in self.models:
            out_dir = create_directories(evaluation_path, "group_" + str(model.id))
            model.preprocessor.data_io.output_path = out_dir
            cb_list = []
            if (not isinstance(model, ModelGroup)):
                #this child is a leaf. ensure correct storage.
                cb_model = ModelCheckpoint(os.path.join(out_dir, "model.hdf5"),
                                           monitor="val_loss", verbose=1,
                                           save_best_only=True, mode="min")
                cb_list = callbacks + [cb_model]
            else:
                cb_list = callbacks
            model.reset()
            model.evaluate(training_samples, validation_samples, evaluation_path=out_dir, epochs=epochs, iterations=iterations, callbacks=callbacks)
    
    def reset(self):
        for model in self.models: #propagate
            model.reset()
    
    def copy(self):
        return ModelGroup([model.copy() for model in self.models], self.preprocessor, False) #truth is implied and it accelerates cloning
    
    # Dump model to file
    def dump(self, file_path):
        subdir = create_directories(file_path, "group_" + str(self.id))
        
        with open(os.path.join(subdir, "metadata.json"), "w") as f:
            json.dump(f, {"type": "group"})
        
        for model in self.models:
            model.dump(subdir)

    # Load model from file
    def load(self, file_path, custom_objects={}):
        collection = [dir for dir in os.listdir(file_path) if os.isdir(dir)]
        
        for obj in collection:
            metadata = {}
            metadata_path = os.path.join(obj, "metadata.json")
            if os.exists(metadata_path):
                with open(metadata_path, "w") as f:
                    metadata = json.load(f)
            model = None
            if "type" in metadata.keys() and metadata["type"] == "group":
                model = ModelGroup([], self.preprocessor)
            else:
                model = Neural_Network(self.preprocessor) #needs handling of arbitrary types. some sort of model agent
            model.load(obj)
            self.models.append(model)