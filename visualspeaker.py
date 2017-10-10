import timeit
import numpy as np
import scipy.fftpack
from scipy.io import wavfile
import sys
import pygame
import math
import time, threading
import queue
import socket

q = queue.Queue()
selected_song = ""
song_selected = False
transferring = False

#background thread to establish a connection with the phone, and then listen for commands
def socketProcess():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while 1:
        #outer loop, first establish connection, then handle input
        while 1:
            try:
                client_socket.connect(('192.168.49.1', 8888))
                break
            except ConnectionRefusedError:
                #print("Connection Refused...")
                time.sleep(1)
        while 1:
			#receive instructions from phone, then decode and handle
            data = client_socket.recv(512)
            if (data.decode() == "pause"):
                q.put("pause")
            elif (data.decode() == "play"):
                q.put("play")
                print("play")
            elif (data.decode() == ""):
                print("Stopping...")
                client_socket.close()
                break
            elif ("change" in data.decode()):
                q.put(data.decode())
                strlist = data.decode().split()
                filename = strlist[1]
                global selected_song
                selected_song = filename
                global song_selected
                song_selected = True
                q.put("play")
                
            elif ("transfer" in data.decode()):
                print("DING")
                client_socket.settimeout(3.0)
                strlist = data.decode().split()
                filename = strlist[1]
                global transferring
                transferring = True
                f = open(filename, 'wb')
                while 1:
                    try:
                        data = client_socket.recv(1024)
                    except socket.timeout:
                        print("Done")
                        break
                    f.write(data)

                f.close()
                client_socket.settimeout(None)
                transferring = False

            else:
                print ("received: ", data.decode())

#This object handles the creation and updating of the graphics
class Display:
    def __init__(self):
        pygame.init()
        self.bg = 0, 0, 0
        self.barcolor = 0, 0, 100
        self.size = width, height = 1280, 720
        self.icon = pygame.image.load("transfer.png")
        self.icon_rect = pygame.Rect(0, 0, 64, 64)
        self.screen = pygame.display.set_mode(self.size, pygame.FULLSCREEN)
        self.bars = []
        for i in range(0, 8):
            self.bars.append(Bar(128 + 128*i, 128, 5, 720))
    def update(self, data):
        #print("update called")
        for event in pygame.event.get():
            if event.type == pygame.QUIT: sys.exit()
        
        self.screen.fill(self.bg)
        global transferring
        if transferring == True:
            #self.screen.blit(self.icon, self.icon_rect)
            pygame.draw.rect(self.screen, (50, 50, 50), (0, 0, 64, 64))
        for i in range(0,8):
            #update bar height, then draw
            newHeight = 5 + int(data[i]*2500)
            if newHeight > 600:
                newHeight = 600
            self.bars[i].setHeight(newHeight)
            pygame.draw.rect(self.screen, self.barcolor, self.bars[i].getRect())
            
        pygame.display.flip()
        pygame.display.update()
    def reset(self):
        self.screen.fill(self.bg)
        for i in range(0,8):
            self.bars[i].setHeight(5)
            pygame.draw.rect(self.screen, self.barcolor, self.bars[i].getRect())
        pygame.display.flip()
        pygame.display.update()
        
        
        
#This object holds the dimensions for the bars that are drawn on the screen
class Bar:
    def __init__(self, left, width, height, base):
        self.left = left
        self.width = width
        self.base = base
        self.top = base - height
        self.height = height
    def setHeight(self, height):
        self.top = self.base - height
        self.height = height
    def getRect(self):
        return (self.left, self.top, self.width, self.height)

#This object handles the analysis of the waveform music file and generates data to be plotted graphically as the song is playing
class FFTAnalysis:
    def __init__(self, soundfile, interval=200):
        #print("test")
        self.data = []
        sampFreq, snd = wavfile.read(soundfile)
        snd = snd / (2.**15)
        duration = len(snd)/sampFreq                #seconds of the song
        ite = np.floor(duration*1000/interval)      #number of iterations
        samp_int = sampFreq/1000*interval           #number of samples per interval
        #It must be integer
        j = 1
        while (j != ite):
            s1 = snd[j*samp_int-samp_int:j*samp_int,0] + snd[j*samp_int-samp_int:j*samp_int,1]
    
            n = len(s1) 
            p = scipy.fftpack.fft(s1) # take the fourier transform
    
            nUniquePts = int(np.ceil((n+1)/2.0))
            p = p[0:nUniquePts]
            p = abs(p)
                
            p = p / float(n) # scale by the number of points so that
            # the magnitude does not depend on the length 
            # of the signal or on its sampling frequency  
            p = p**2  # square it to get the power 
    
            # multiply by two (see technical document for details)
            # odd nfft excludes Nyquist point
            if n % 2 > 0: # we've got odd number of points fft
                p[1:len(p)] = p[1:len(p)] * 2
            else:
                p[1:len(p) -1] = p[1:len(p) - 1] * 2 # we've got even number of points fft

            freqArray = np.log(np.arange(0, nUniquePts, 1.0) * (sampFreq / n));
            logarr = [0]
            logarr.extend(np.logspace(0, math.log(nUniquePts, 10), 8))
            currData = []
            """ Old way, evely split between 8
            for i in range(0, 8):
                start = i*nUniquePts/8
                stop = (i+1)*nUniquePts/8 - 1
                currData.append(np.amax(p[start:stop]))
            #second oldest way"""
            for i in range(0,8):
                start = int(logarr[i])
                stop = int(logarr[i+1])
                currData.append(np.amax(p[start:stop]))
            
            
            self.data.append(currData)
            j += 1

def main():
    #first set up socket thread
    thread = threading.Thread(target=socketProcess)
    thread.daemon = True
    thread.start()

    running = False #Variable determines whether playing or paused. Starts paused

    pygame.mixer.init()
        
    interval = 50
    win = Display()

    global song_selected
    global selected_song

    pygame.mouse.set_visible(False) #hides ugly cursor for fullscreen

    #selected_song = "04_Harder_Better_Faster_Stronger.wav"
 

    #main loop
    while 1:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    sys.exit()

        win.update((0,0,0,0,0,0,0,0))

        if (song_selected == True):
            #load current song
            pygame.mixer.music.load(selected_song)
            pygame.mixer.music.play()
            pygame.mixer.music.pause()

            #init data for current song
            ffta = FFTAnalysis(selected_song, interval)
            starttime = time.time()
            prevtick = starttime
            tickindex = 0
            nticks = len(ffta.data)
            
			#At a specified interval (50ms), handle input from a task queue, and update graphics based on the next point of data
            while tickindex < nticks:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        sys.exit()
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            sys.exit()
                        
                if ((time.time() - prevtick)*1000 > interval):
                    if (not q.empty()):
                        task = q.get()
                        if (task == "play"):
                            print ("play handled")
                            running = True
                            pygame.mixer.music.unpause()
                        elif (task == "pause"):
                            running = False
                            pygame.mixer.music.pause()
                            win.reset()
                        elif ("change" in task):
                            running = False
                            pygame.mixer.music.stop()
                            break
                        
                    prevtick = time.time()
                        
                    if (running == True):
                        win.update(ffta.data[tickindex])
                        tickindex += 1

            if tickindex >= nticks:
                song_selected = False
                    
        win.reset()
        #wait for next song
        
        

if __name__ == '__main__':
    main()
