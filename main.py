#!/usr/bin/env python

import os
import sys
import cv2
import pathlib
import threading
import numpy as np
from tracker import auto_tracker
from extraction import extraction
from Interface.user import MyWidget
from PyQt5.QtGui import QIcon, QPixmap
from eye_tracking.Track import fast_tracker
from video_construct import video_construct
from PyQt5 import uic, QtCore, QtGui, QtWidgets
from Interface.video_player import VideoPlayer

class main(QtWidgets.QMainWindow):
    def __init__(self, video = None, file = None):
        #Dictionary including index and picture for each
        super().__init__()
        self.pic_collection = {}
        self.collection = {}
        self.p_r_collection = {}
        self.wanted = None
        self.MyWidget = None
        self.width = 0
        self.height = 0

        # Video for the patient
        self.Video = None
        # Data retrived by the machine
        self.File = None


        self.f_rate = 60 #Should be presented in the file. Don't know if could be gotten using python
        #Factor that resize the image to make the program run faster
        self.size_factor = (4,4)
        self.cropping_factor = [[0,0],[0,0]] #(start_x, end_x, start_y, end_y)
        self.path = str(pathlib.Path(__file__).parent.absolute())+'/input/video.mp4'
        uic.loadUi('Interface/dum.ui', self)
        self.setWindowTitle('Pupil Tracking')
        self.Analyze.setEnabled(False)
        self.Demo.setEnabled(False)
        self.Generate.clicked.connect(self.generate)
        self.Analyze.clicked.connect(self.analyze)
        self.Terminate.clicked.connect(self.terminate)
        self.VideoText.setText('input/run1.mov')
        self.FileText.setText('input/10997_20180818_mri_1_view.csv')
        self.Demo.clicked.connect(self.video_call)
        self.player = VideoPlayer(self, self.path)
        self.show()


    def terminate(self):
        print('Implement later')

    #The whole purpose of this function is to use multi-threading
    def tracking(self, ROI):
        #Initialize the eye_tracker
        auto_tracker(self.Video, ROI)

    def video_call(self):
        #Construct all thr available files to video to be displayed
        video_construct()
        self.player.setWindowTitle("Player")
        self.player.resize(600, 400)
        self.player.show()

    def analyze(self):
        self.Analyze.setEnabled(False)
        self.Demo.setEnabled(True)
        # self.Generate.setEnabled(True)
        print(self.MyWidget.begin)
        print(self.MyWidget.end)

        self.cropping_factor[0][0] = self.MyWidget.begin.x()
        self.cropping_factor[0][1] = self.MyWidget.end.x()
        self.cropping_factor[1][0] = self.MyWidget.begin.y()
        self.cropping_factor[1][1] = self.MyWidget.end.y()

        #Trurns out the cropping of x and y is reversed!!!
        new_dimension = cv2.imread('input/chosen_pic.png')\
        [self.cropping_factor[1][0] : self.cropping_factor[1][1],\
        self.cropping_factor[0][0] : self.cropping_factor[0][1]]

        ROI = (self.cropping_factor[0][0],\
               self.cropping_factor[1][0],\
               self.cropping_factor[0][1] - self.cropping_factor[0][0],\
               self.cropping_factor[1][1] - self.cropping_factor[1][0]) 

        #Save file for the input of machine learning class
        # cv2.imwrite('input/search_case.png', new_dimension)

        print(ROI)
        t2 = threading.Thread(target=self.tracking, args=(ROI,))
        t2.start()
        self.label_6.setText(str(int(self.label_6.text())+1))
        # t2.join()

    #This function also calls another thread which saves all video generated images in the output file
    def generate(self):
        self.Analyze.setEnabled(True)
        self.Generate.setEnabled(False)
        self.Video = self.VideoText.text()
        self.File = self.FileText.text()
        #Check validity
        if not os.path.exists(self.Video): #or not os.path.exists(File):
            print(f"Video file '{self.Video}' does not exist")
            return
        if not os.path.exists(self.File):
            print(f"Text file '{self.File}' does not exist")
            return

        # disable line editing once we've picked our files to avoid confusion
        self.VideoText.setEnabled(False)
        self.FileText.setEnabled(False)

        print('Start writing images to the file\n')
        print('start reading in files')

        #self.collection = {cue, vgs, dly, mgs}
        self.collection = extraction(self.File)
        # print(self.collection)
        #Try get the video frame next time
        for key, data in self.collection.items():
            self.p_r_collection[key] = [element * self.f_rate for element in data]
        print(self.p_r_collection)

        #Create a thread to break down video into frames into out directory
        t1 = threading.Thread(target=self.to_frame, args=(self.Video, None))
        #Only run the thread when the file is empty
        if not os.path.exists('output'):
            os.makedirs('output')
        dirls = os.listdir('output')
        if len(dirls) == 0:
            self.label_6.setText(str(int(self.label_6.text())+1))
            # t1.start()

        self.wanted = self.to_frame(self.Video)
        #Just to check for extreme cases, could be ignored for normal cases.
        if self.wanted != None:
            sample = self.pic_collection[self.wanted]
            #Saved because user.py actually need to read the picture to create the widget
            #Since the picture are all sized down by 4, it needed to be sized up here in order for the user to see
            # sample = cv2.resize(sample,(int(self.width)*self.size_factor[0], int(self.height)*self.size_factor[1]))

            cv2.imwrite('input/chosen_pic.png', sample)
        self.MyWidget = MyWidget(self)
        self.LayVideo.addWidget(self.MyWidget)

    #This function is only for choosing the best open-eye picture
    #Maybe its a bit redundant, try to fix later
    def to_frame(self, video, limit = 500):
        maximum = 0
        wanted = 0
        #i counts the image sequence generated from the video file
        i = 0
        cap = cv2.VideoCapture(video)
        while(cap.isOpened()):
            ret, frame = cap.read()
            if ret == False:
                break
            #Need to figure out a way to downscale the image to make it run faster
            self.height = frame.shape[0]
            self.width = frame.shape[1]

            # frame = cv2.resize(frame,(int(self.width/self.size_factor[0]), int(self.height/self.size_factor[1])))
            if limit != None:
                #Test for the non-blinking image(Find image with the larggest dark space)
                if len(np.where(frame < 100)[0]) > maximum and i < limit:
                    maximum = len(np.where(frame < 100)[0])
                    wanted = i
                #Add a limit to it so it could run faster when testing
                #We need a perfect opened_eye to run machine learning program on to determine the parameters.
                if i > limit:
                    return wanted

                self.pic_collection[i] = frame
                print("image scanned: ", i)

            else: 
                cv2.imwrite('output/%d.png'%i, frame)

            i+=1
        print('Thread 2 finished')
        return wanted

if __name__ == '__main__':
    #Later put into the user interface

    App = QtWidgets.QApplication([])
    WINDOW = main()
    sys.exit(App.exec_())
