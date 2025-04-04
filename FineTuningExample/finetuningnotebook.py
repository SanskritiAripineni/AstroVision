# -*- coding: utf-8 -*-
"""FinetuningNotebook.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1s9g8GV7RmUXIOE3FhAt-k2UMPLGdF5Yj

# This is an example notebook on how to use Optuna for finetuning
"""

from google.colab import drive
drive.mount('/content/drive')

!pip install optuna

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sea
import optuna
import random

import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D
from tensorflow.keras.optimizers import Adam, AdamW
from tensorflow.keras.layers import LeakyReLU
from tensorflow.keras.callbacks import LearningRateScheduler

from sklearn.metrics import classification_report, confusion_matrix
from IPython.display import display
from PIL import Image

import warnings
warnings.filterwarnings("ignore")

WIDTH, HEIGHT = 224, 224
BATCH_SIZE = 32
EPOCHS = 5
DATA_PATH = '/content/drive/MyDrive/AstroVisionData/spaceImages'

#data augmentation
train_datagen = ImageDataGenerator(
    rescale=1./255,
    rotation_range=20,
    width_shift_range=0.2,
    height_shift_range=0.2,
    shear_range=0.2,
    zoom_range=0.2,
    horizontal_flip=True,
    fill_mode='nearest',
    validation_split=0.2
)

def set_seed(seed_value=3126):
    random.seed(seed_value)
    np.random.seed(seed_value)
    tf.random.set_seed(seed_value)

set_seed()

def prepare_train_val_generators(batch_size):
  train_generator = train_datagen.flow_from_directory(
      DATA_PATH,
      target_size=(WIDTH, HEIGHT),
      batch_size=batch_size,
      class_mode='categorical',
      subset='training')

  validation_generator = train_datagen.flow_from_directory(
    DATA_PATH,
    target_size=(WIDTH, HEIGHT),
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    subset='validation'
  )
  return train_generator, validation_generator

def base_model_objective(trial):
  ## Define distributions of hyperparams
  ## log is used for ensuring faster convergence for skewed distributions
  batch_size_    = trial.suggest_int("batch_size", 8, 64)
  learning_rate_ = trial.suggest_float("learning_rate", 1e-5, 1e-2, log=True)
  dense_input_   = trial.suggest_int("dense_input", 128, 4096, step=128)
  activation_    = trial.suggest_categorical("activation", ["relu", "leakyrelu", "swish"])
  optimizer_     = trial.suggest_categorical("optimizer", ["Adam", "AdamW"])
  weight_decay_  = trial.suggest_float("weight_decay", 1e-8, 1e-2, log=True)
  beta1_         = trial.suggest_float("beta1", .885, .999) # momentum
  beta2_         = trial.suggest_float("beta2", .885, .999) # momentum
  if activation_=="leakyrelu":
    leakyrelu_alpha_  = trial.suggest_float("leakyrelu_alpha", .05, .5, log=True)

  ## Gets model
  base_model = MobileNetV2(weights='imagenet', include_top=False, input_shape=(224, 224, 3))
  x = base_model.output
  x = GlobalAveragePooling2D()(x)

  ## Allocates the proper activation function as selected by the algorithm
  if activation_ == "leakyrelu":
    x = Dense(dense_input_)(x)
    x = LeakyReLU(alpha=leakyrelu_alpha_)(x)
  elif activation_ == "swish":
        x = Dense(dense_input_, activation=tf.nn.swish)(x)
  else:
    x = Dense(dense_input_, activation=activation_)(x)
  predictions = Dense(6, activation='softmax')(x)
  model = Model(inputs=base_model.input, outputs=predictions)

  ## Allocates the proper optimizer
  if optimizer_=="Adam":
    optimizer_ = Adam(learning_rate_)
  else:
    optimizer_ = AdamW(learning_rate_, weight_decay_, beta1_, beta2_)

  ## Prepares train and validation generator from algorithm's batch size
  train_generator, validation_generator = prepare_train_val_generators(batch_size_)

  ## Trains model for epochs times
  epochs = 30
  for layer in base_model.layers:
    layer.trainable = False
  model.compile(optimizer=optimizer_, loss='categorical_crossentropy', metrics=['accuracy'])
  history = model.fit(train_generator, epochs=epochs, validation_data=validation_generator)

  ## Extracts validation accuracy for Optuna to check how good its chosen hyperparams are
  val_acc = history.history["val_accuracy"][-1]
  return val_acc

## Objective is to maximize accuracy!
study = optuna.create_study(study_name="baseline_params_search", direction="maximize")
## Runs the search for hyperparams
study.optimize(base_model_objective, n_trials=100)

print("Best parameters:", study.best_params)
print("Best validation accuracy:", study.best_value)