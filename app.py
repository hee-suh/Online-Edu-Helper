# Flask 웹 서버 구축에 필요한 라이브러리
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS
import time

# Object Detection Webcam Inference
import numpy as np
import os
import six.moves.urllib as urllib
import sys
import tarfile
import tensorflow as tf
import zipfile

from collections import defaultdict
from io import StringIO
from matplotlib import pyplot as plt
from PIL import Image
from IPython.display import display
import pathlib

from object_detection.utils import ops as utils_ops
from object_detection.utils import label_map_util
from object_detection.utils import visualization_utils as vis_util

import cv2
# cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

YOUR_MODEL_PATH = 'C:/Users/dataset/fine_tuned_model/'
YOUR_DATA_PB_PATH = 'C:/Users/dataset'
YOUR_MODEL_NAME = 'x3_10000'

app = Flask(__name__, static_url_path='', static_folder='client/build')
CORS(app)

@app.route("/", defaults={'path':''})
def serve(path):
    return send_from_directory(app.static_folder,'index.html')

selected_object = []
detected_object = []

# Patch the location of gfile
tf.gfile = tf.io.gfile

# For Mac m1
# tf.config.experimental.set_visible_devices([], 'GPU')

#--- Model Preparation ---#
def load_model(model_name):
    model_dir = YOUR_MODEL_PATH + model_name  # efficientdet_d1
    
    model_dir = pathlib.Path(model_dir)/"saved_model"
    print('[INFO] Loading the modle from '+ str(model_dir))
    model = tf.saved_model.load(str(model_dir))

    return model

# List of the strings that is used to add correct label for each box
PATH_TO_LABELS = os.path.join(YOUR_DATA_PB_PATH, 'school-supplies_label_map.pbtxt')
category_index = label_map_util.create_category_index_from_labelmap(PATH_TO_LABELS)

#--- Detection ---#
model_name = YOUR_MODEL_NAME
print('[INFO] Downloading model and loading to network : '+ model_name)
detection_model = load_model(model_name)

def run_inference_for_single_image(model, image):
    image = np.asarray(image)
    # The input needs to be a tensor, convert it using 'tf.convert_to_tensor'
    input_tensor = tf.convert_to_tensor(image)
    # The model expects a batch of images , so add an axis with 'tf.newaxis'
    input_tensor = input_tensor[tf.newaxis,...]

    # Run inference
    model_fn = model.signatures['serving_default']
    output_dict = model_fn(input_tensor)

    # All outputs are batches tensors
    # Convert to numpy arrays , and take index [0] to remove the batch dimension
    # We're only interested in the first num_detections
    num_detections = int(output_dict.pop('num_detections'))
    output_dict = {key:value[0,:num_detections].numpy()
                   for key, value in output_dict.items()}
    output_dict['num_detections'] = num_detections

    # detection_classes should be ints
    output_dict['detection_classes'] = output_dict['detection_classes'].astype(np.int64)

    # Handle models with masks
    if 'detection_masks ' in output_dict:
        # Reframe the the bbox mask to the image size
        detection_masks_reframed = utils_ops.reframe_box_masks_to_image_masks(
            output_dict['detection_masks'], output_dict['detection_boxes'],
            image.shape[0], image.shape[1])
        detection_masks_reframed = tf.cast(detection_masks_reframed > 0.5,
                                           tf.uint8)
        output_dict['detection_masks_reframed'] = detection_masks_reframed.numpy()
        
    return output_dict

def run_inference(model):
    global selected_object, detected_object
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        print("success")
    else:
        print("no camera")
        return -1
    while True:
        ret, image_np = cap.read()
        # Actual detection
        output_dict = run_inference_for_single_image(model, image_np)
        TF = [False] * output_dict['num_detections']
        if len(selected_object) == 0:
            cv2.imwrite('object_detection.jpg', cv2.resize(image_np, (800,600)))
        else:
            for i in selected_object:
                TF = np.any([TF, output_dict['detection_classes'] == i], axis = 0)
            
            # 선택된 object detection -> 결과
            TF_S = np.all([TF, output_dict['detection_scores'] > 0.5], axis = 0)
            detected_object += list(output_dict['detection_classes'][TF_S])
            
            # 선택된 object detection -> Visualize Box를 위한 처리
            output_dict['detection_boxes'] = output_dict['detection_boxes'][TF]
            output_dict['detection_classes'] = output_dict['detection_classes'][TF]
            output_dict['detection_scores'] = output_dict['detection_scores'][TF]

            # Visualization of the results of a detection
            vis_util.visualize_boxes_and_labels_on_image_array(
                image_np,
                output_dict['detection_boxes'],
                output_dict['detection_classes'],
                output_dict['detection_scores'],
                category_index,
                instance_masks=output_dict.get('detection_masks_reframed', None),
                use_normalized_coordinates=True,
                line_thickness=8)
            cv2.imwrite('object_detection.jpg', cv2.resize(image_np, (800,600)))
        yield (b'--frame\r\n' 
            b'Content-Type: image/jpeg\r\n\r\n' + open('object_detection.jpg', 'rb').read() + b'\r\n')
                   


object = {"book": 1, "face": 2, "glue": 3, "ocarina": 4, "pen": 5, 
          "phone": 6, "recorder": 7, "ruler": 8, "scissors": 9}

object_name = {1: "book", 2: "face", 3: "glue", 4: "ocarina", 5: "pen",
               6: "phone", 7: "recorder", 8: "ruler", 9: "scissors"}

return_dic = {"id": 1, "name": "서희", "attendance": False, "focus": True, "material":[]}

@app.route("/process", methods=['GET', 'POST'])
def process():
    global selected_object, detected_object
    selected_object = []
    detected_object = []
    
    content = request.json
    if content['attendance']:
        selected_object.append(object["face"])
    if content['focus']:
        selected_object.append(object["phone"])
    if content['material']:
        for m in content['material']:
            selected_object.append(object[m])

    time.sleep(10) # 시간 딜레이
    while not detected_object:
        continue
    
    detected_object = list(set(detected_object))
    
    if object["face"] in detected_object:
        return_dic["attendance"] = True
    
    if object["phone"] in detected_object:
        return_dic['focus'] = False
        
    for obj in detected_object:
        if obj != 2 or obj != 6:
            return_dic['material'].append(object_name[obj])
            
    return jsonify(return_dic)


def gen(): 
   """Video streaming generator function.""" 
   while True: 
       ret, frame = cap.read() 
       cv2.imwrite('pic.jpg', frame) 
       yield (b'--frame\r\n' 
              b'Content-Type: image/jpeg\r\n\r\n' + open('pic.jpg', 'rb').read() + b'\r\n')


@app.route("/video_feed")
def video_feed():
    return Response(run_inference(detection_model), 
                   mimetype='multipart/x-mixed-replace; boundary=frame')
    
    
if __name__ == '__main__':
     app.run('localhost', port=5000)