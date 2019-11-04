# coding: UTF-8

"""
pyCamRec
An open-source software written in Python
  for saving video or snapshot images from cams, attached via USB cables.

This program was coded and tested in macOS 10.13.

Jinook Oh, Cognitive Biology department, University of Vienna
October 2019.

Dependency:
    wxPython (4.0)
    NumPy (1.14)
    OpenCV (3.4)

------------------------------------------------------------------------
Copyright (C) 2019 Jinook Oh, W. Tecumseh Fitch
- Contact: jinook.oh@univie.ac.at, tecumseh.fitch@univie.ac.at

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License along
with this program.  If not, see <http://www.gnu.org/licenses/>.
------------------------------------------------------------------------


Changelog
------------------------------------------------------------------------
v.0.1: (2019.11.04)
  - Initial development.
"""

from os import path, getcwd, mkdir
from sys import argv
from copy import copy
from threading import Thread
from datetime import timedelta
from time import time, sleep
import queue

import cv2, wx, wx.adv
import wx.lib.scrolledpanel as SPanel
import numpy as np

from fFuncNClasses import get_time_stamp, GNU_notice, writeFile, getWXFonts
from fFuncNClasses import setupStaticText, updateFrameSize, getCamIdx
from fFuncNClasses import str2num, add2gbs, PopupDialog

DEBUG = False
CWD = getcwd()
__version__ = "0.1"

#=======================================================================

class Cam:
    """ class for retrieving images from cam
    
    Attributes:
        Each attribute is commented in 'setting up attributes' section.
    """

    def __init__(self, parent, cIdx, logFile):
        if DEBUG: print("Cam.__init__()")
        ##### beginning of setting up attributes -----
        self.parent = parent # parent
        self.cIdx = cIdx # index of cam
        self.cap = cv2.VideoCapture(cIdx) # video capture
        sleep(0.3) # some delay for cam's initial auto-adjustment
        self.logFile = logFile # log file
        ### get frame size
        for i in range(10):
            ret, frame = self.cap.read()
            if ret == True:
                self.fSz = (frame.shape[1], frame.shape[0]) # frame size
                self.initFrame = frame # initial frame
                break
            sleep(0.01)
        self.outputFormat = "video" # video or image
        self.fpsLimit = 30 # Upper limit of frames per second
        self.ssIntv = 1.0 # snapshot (saving image from Cam) interval in seconds
        self.imgExt = "jpg" # file type when saving frames to images
        ##### end of setting up attributes -----
    
    #-------------------------------------------------------------------

    def run(self, q2m, q2t, recFolder=""):
        """ Function for thread to retrieve image
        and store it as video or image
        
        Args:
            q2m (queue.Queue): Queue to main thread to return message.
            q2t (queue.Queue): Queue from main thread.
            recFolder (str): Folder to save recorded videos/images.
        
        Returns:
            None
        """
        if DEBUG: print("Cam.run()")

        # --------------------------------------------------------------
        def startRecording(cIdx, 
                           oFormat, 
                           recFolder, 
                           fps, 
                           fSz, 
                           logFile, 
                           fpsLimit, 
                           ssIntv):
            # Define the codec and create VideoWriter object
            #fourcc = cv2.VideoWriter_fourcc(*'X264')
            fourcc = cv2.VideoWriter_fourcc(*'avc1') # for saving mp4 video
            #fourcc = cv2.VideoWriter_fourcc('x','v','i','d')
            log = "%s,"%(get_time_stamp())
            log += " Cam-%.2i recording starts"%(cIdx)
            log += " [%s]"%(oFormat)
            if oFormat == 'video':
                ofn = "output_%.2i_%s.mp4"%(cIdx, get_time_stamp())
                ofn = path.join(recFolder, ofn)
                # get average of the past 10 fps records
                ofps = int(np.average(fps[:10]))
                # set 'out' as a video writer
                out = cv2.VideoWriter(ofn, fourcc, ofps, fSz, True)
                log += " [%s] [FPS: %i] [FPS-limit: %i]\n"%(ofn, ofps, fpsLimit)
            elif oFormat == 'image':
                ofn = "output_%.2i_%s"%(cIdx, get_time_stamp())
                ofn = path.join(recFolder, ofn)
                # 'out' is used as an index of a image file
                out = 1
                log += " [%s] [Snapshot-interval: %s]\n"%(ofn, str(ssIntv))
                if not path.isdir(ofn): mkdir(ofn)
            writeFile(logFile, log)
            return out, ofn

        # --------------------------------------------------------------
        def stopRecording(out, cIdx, logFile):
            if isinstance(out, cv2.VideoWriter): out.release()
            out = None
            ### log
            log = "%s,"%(get_time_stamp())
            log += " Cam-%.2i recording stops\n"%(cIdx)
            writeFile(logFile, log)
            return out

        # --------------------------------------------------------------

        q2tMsg = '' # queued message sent from main thread
        ofn = '' # output file or folder name
        out = None # videoWriter or index for image file
        fpIntv = 1.0/self.fpsLimit # interval between each frame
        lastFrameProcTime = time()-fpIntv # last frame processing time
        imgSaveTime = time()-self.ssIntv # last time image was saved
        fpsRecTime = time(); fps = [0]

        ##### [begin] infinite loop of thread -----
        while(self.cap.isOpened()):
            
            ### limit frame processing when output-format is video
            if self.outputFormat == 'video' and self.fpsLimit != -1:
                if time()-lastFrameProcTime < fpIntv:
                    sleep(0.001)
                    continue
                lastFrameProcTime = time()
            
            ### fps
            if time()-fpsRecTime > 1:
                print("[c%.2i] FPS: "%(self.cIdx), fps[-1])
                fps.append(0)
                # keep the past 10 fps records (except the current counting fps)
                
                fpsRecTime = time()
            else:
                fps[-1] += 1
            
            ### process queue message (q2t)
            if q2t.empty() == False:
                try: q2tMsg = q2t.get(False)
                except: pass
            if q2tMsg != "":
                if q2tMsg == "quit":
                    break
                elif q2tMsg == 'rec_init':
                    if out == None:
                        out, ofn = startRecording(self.cIdx, 
                                                  self.outputFormat, 
                                                  recFolder,
                                                  fps, 
                                                  self.fSz, 
                                                  self.logFile,
                                                  self.fpsLimit,
                                                  self.ssIntv)
                elif q2tMsg == 'rec_stop':
                    if out != None:
                        out = stopRecording(out, self.cIdx, self.logFile)
                q2tMsg = ""
            
            ### retrieve a frame image and process
            ret, frame = self.cap.read()
            if ret==True: # frame image retrieved
                if out != None:
                    if self.outputFormat == 'video':
                        out.write(frame) # write a frame to video
                    elif self.outputFormat == 'image':
                        if time()-imgSaveTime >= self.ssIntv:
                        # interval time has passed
                            fp = path.join(ofn, "f%06i.%s"%(out, self.imgExt))
                            cv2.imwrite(fp, frame) # save image
                            out += 1
                            imgSaveTime = time()
                # send frame via queue to main
                q2m.put([self.cIdx, frame], True, None)
            else:
                break
        ##### [end] infinite loop of thread -----
        
        if out != None and type(out) != int: out.release()
    
    #-------------------------------------------------------------------

    def close(self):
        """ Release VideoCapture of this Cam
        
        Args: None
        
        Returns: None
        """
        if DEBUG: print("Cam.close()")

        self.cap.release()
    
    #-------------------------------------------------------------------
    
#=======================================================================

class CamRecFrame(wx.Frame):
    """ Frame for CamRecApp
    
    Attributes:
        Each attribute is commented in 'setting up attributes' section.
    """

    def __init__(self):
        if DEBUG: print("CamRecFrame.__init__()")

        ### init frame
        w_pos = [0, 25]
        wg = wx.Display(0).GetGeometry()
        wSz = (wg[2], int(wg[3]*0.9))
        wx.Frame.__init__(
              self,
              None,
              -1,
              "pyCamRec v.%s"%(__version__),
              pos = tuple(w_pos),
              size = tuple(wSz),
              style=wx.DEFAULT_FRAME_STYLE^(wx.RESIZE_BORDER|wx.MAXIMIZE_BOX),
                         )
        self.SetBackgroundColour('#333333')

        ### set app icon
        self.tbIcon = wx.adv.TaskBarIcon(iconType=wx.adv.TBI_DOCK)
        icon = wx.Icon("icon.ico")
        self.tbIcon.SetIcon(icon)
        
        ##### beginning of setting up attributes -----
        self.logFile = "pCR_log.txt"
        self.recFolder = "recordings"
        self.w_pos = w_pos # window position
        self.wSz = wSz # window size
        self.fonts = getWXFonts(initFontSz=8, numFonts=3)
        self.cIndices = getCamIdx(maxNCam=4) # indices of cams
        if self.cIndices == []:
            msg = "No usable cams is attached."
            wx.MessageBox(msg, 'Info', wx.OK | wx.ICON_INFORMATION)
            self.Destroy()
        pi = self.setPanelInfo()
        self.pi = pi # pnael information
        self.gbs = {} # for GridBagSizer
        self.panel = {} # panels
        self.timer = {} # timers
        self.cams = {} # Cam class instances
        self.th = [] # List of threads for each cam
        self.q2m = queue.Queue() # queue to get massage from a thread
        self.q2t = [] # list of queues to send massage to a thread
        for ci in self.cIndices:
            self.cams[ci] = Cam(self, ci, self.logFile)
            self.th.append(-1)
            self.q2t.append(queue.Queue())
        self.oCIdx = [] # opened cam indices
        self.nCOnSide = 0 # number of cam images on one side
        # each cam's frame size for displaying
        dCSz = copy(pi["rp"]["sz"]) # frame size of a cam for displaying
        self.dispCSz = dCSz
        # numpy array for displaying cam images
        self.dispArr = np.zeros(shape=(dCSz[1], dCSz[0], 3), dtype=np.uint8)
        self.is_recording = False # whether it's currently recording or not
        self.rSTime = -1 # recording start time
        self.rDur_sTxt = None # for showing recording duration
        self.preview_sBmp = None # for showing preview of selected cam
        self.disp_sBmp = None # for showing recording view of cam(s)
        ##### end of setting up attributes -----
        if not path.isdir(self.recFolder): # recording folder doesn't exist
            mkdir(self.recFolder) # make one
        if not path.isfile(self.logFile): # log file doesn't exist
            ### make header in log file
            logHeader = "Timestamp, Message\n"
            logHeader += "#-------------------------------------------------\n"
            writeFile(self.logFile, logHeader) # write header

        ### create panels
        for pk in pi.keys():
            self.panel[pk] = SPanel.ScrolledPanel(
                                                  self,
                                                  name="%s_panel"%(pk),
                                                  pos=pi[pk]["pos"],
                                                  size=pi[pk]["sz"],
                                                  style=pi[pk]["style"],
                                                 )
            self.panel[pk].SetBackgroundColour(pi[pk]["bgCol"])

        ##### beginning of setting up UI panel interface -----
        bw = 5 # border width for GridBagSizer
        nCol = 4 # number columns
        uiSz = pi["ui"]["sz"]
        hlSz = (int(uiSz[0]*0.95), -1) # size of horizontal line separator
        self.gbs["ui"] = wx.GridBagSizer(0,0)
        row = 0
        col = 0
        sTxt = setupStaticText(
                            self.panel["ui"],
                            "Cam index: ",
                            font=self.fonts[2],
                            )
        add2gbs(self.gbs["ui"], sTxt, (row,col), (1,1))
        col += 1
        _choices = [str(x) for x in self.cIndices]
        _choices.insert(0, '')
        cho = wx.Choice(
                            self.panel["ui"],
                            -1,
                            name="camIdx_cho",
                            choices=_choices,
                       )
        cho.Bind(wx.EVT_CHOICE, self.onChoice)
        add2gbs(self.gbs["ui"], cho, (row,col), (1,1))
        row += 1; col = 0
        sTxt = setupStaticText(
                            self.panel["ui"],
                            "Initial frame image:",
                            font=self.fonts[2],
                            )
        add2gbs(self.gbs["ui"], sTxt, (row,col), (1,nCol))
        row += 1; col = 0
        ### set up staticBitmap for preview
        w = int(uiSz[0]*0.95)
        h = int(w/1.333)
        sBmp = wx.StaticBitmap(self.panel["ui"], -1, size=(w,h))
        img = wx.Image(w, h)
        img.SetData(np.zeros((h,w,3),dtype=np.uint8).tostring())
        sBmp.SetBitmap(img.ConvertToBitmap())
        self.preview_sBmp = sBmp
        add2gbs(self.gbs["ui"], sBmp, (row,col), (1,nCol))
        row += 1; col = 0
        sTxt = setupStaticText(
                            self.panel["ui"],
                            "Output format: ",
                            font=self.fonts[2],
                            )
        add2gbs(self.gbs["ui"], sTxt, (row,col), (1,1))
        col += 1
        cho = wx.Choice(
                            self.panel["ui"],
                            -1,
                            name="outputFormat_cho",
                            choices=['video', 'image'],
                       )
        cho.Bind(wx.EVT_CHOICE, self.onChoice)
        add2gbs(self.gbs["ui"], cho, (row,col), (1,1))
        row += 1; col = 0
        sTxt = setupStaticText(
                            self.panel["ui"],
                            "Video FPS upper limit: ",
                            font=self.fonts[2],
                            )
        add2gbs(self.gbs["ui"], sTxt, (row,col), (1,2))
        col += 2
        spin = wx.SpinCtrl(
                            self.panel["ui"],
                            -1,
                            size=(75,-1),
                            min=1,
                            max=60,
                            initial=15,
                            name='videoFPSlimit_spin',
                            style=wx.SP_ARROW_KEYS|wx.SP_WRAP,
                          )
        add2gbs(self.gbs["ui"], spin, (row,col), (1,1))
        row += 1; col = 0
        sTxt = setupStaticText(
                            self.panel["ui"],
                            "Image capture interval (seconds): ",
                            font=self.fonts[2],
                            )
        add2gbs(self.gbs["ui"], sTxt, (row,col), (1,2))
        col += 2
        spin = wx.SpinCtrlDouble(
                            self.panel["ui"],
                            -1,
                            size=(75,-1),
                            min=0.04, # min; 25 fps
                            max=3600,
                            initial=0.5,
                            inc=1, # increment
                            name='ssIntv_spin',
                            style=wx.SP_ARROW_KEYS|wx.SP_WRAP,
                          )
        spin.Disable()
        add2gbs(self.gbs["ui"], spin, (row,col), (1,1))
        row += 1; col = 0
        btn = wx.Button(
                            self.panel["ui"],
                            -1,
                            label="Add",
                            name="addCam_btn",
                            size=(int(uiSz[0]*0.463),-1),
                       )
        btn.Bind(wx.EVT_LEFT_DOWN, self.onButtonPressDown)
        btn.Disable()
        add2gbs(self.gbs["ui"], btn, (row,col), (1,1))
        col += 1
        btn = wx.Button(
                            self.panel["ui"],
                            -1,
                            label="Remove",
                            name="remCam_btn",
                            size=(int(uiSz[0]*0.463),-1),
                       )
        btn.Bind(wx.EVT_LEFT_DOWN, self.onButtonPressDown)
        btn.Disable()
        add2gbs(self.gbs["ui"], btn, (row,col), (1,2))
        row += 1; col = 0
        btn = wx.Button(
                            self.panel["ui"],
                            -1,
                            label="Remove all cams",
                            name="remAllCam_btn",
                            size=(int(uiSz[0]*0.95),-1),
                       )
        btn.Bind(wx.EVT_LEFT_DOWN, self.onButtonPressDown)
        add2gbs(self.gbs["ui"], btn, (row,col), (1,nCol))
        row += 1; col = 0
        sTxt = setupStaticText(
                            self.panel["ui"],
                            "Cams to record (Cam index [output-format(/FPS-limit when video or /interval when image)]):",
                            font=self.fonts[1],
                            wrapWidth=int(uiSz[0]*0.95),
                            )
        add2gbs(self.gbs["ui"], sTxt, (row,col), (1,nCol))
        row += 1; col = 0
        sTxt = setupStaticText(
                            self.panel["ui"],
                            "[]",
                            font=self.fonts[1],
                            name="openCI_sTxt",
                            )
        add2gbs(self.gbs["ui"], sTxt, (row,col), (1,nCol))
        row += 1; col = 0
        add2gbs(self.gbs["ui"],
                wx.StaticLine(self.panel["ui"],
                              -1,
                              size=hlSz,
                              style=wx.LI_HORIZONTAL),
                (row,col),
                (1,nCol)) # horizontal line separator
        row += 1; col = 0
        btn = wx.Button(
                            self.panel["ui"],
                            -1,
                            label="start Recording",
                            name="toggleRec_btn",
                            size=(int(uiSz[0]*0.95), -1),
                       )
        btn.Bind(wx.EVT_LEFT_DOWN, self.onButtonPressDown)
        btn.Disable()
        add2gbs(self.gbs["ui"], btn, (row,col), (1,nCol))
        row += 1; col = 0
        sTxt = setupStaticText(
                            self.panel["ui"],
                            "Recording duration: ",
                            font=self.fonts[2],
                            )
        add2gbs(self.gbs["ui"], sTxt, (row,col), (1,1))
        col += 1
        sTxt = setupStaticText(
                            self.panel["ui"],
                            "0:00:00",
                            font=self.fonts[2],
                            fgColor="#ccccff",
                            bgColor="#000000",
                            )
        self.rDur_sTxt = sTxt
        add2gbs(self.gbs["ui"], sTxt, (row,col), (1,nCol-1))
        self.panel["ui"].SetSizer(self.gbs["ui"])
        self.gbs["ui"].Layout()
        self.panel["ui"].SetupScrolling()
        ##### end of setting up UI panel interface -----

        ##### beginning of setting up recording panel interface -----
        bw = 5 # border width for GridBagSizer
        self.gbs["rp"] = wx.GridBagSizer(0,0)
        row = 0
        col = 0
        sBmp = wx.StaticBitmap(self.panel["rp"], -1, size=pi["rp"]["sz"])
        self.disp_sBmp = sBmp
        self.panel["rp"].SetSizer(self.gbs["rp"])
        self.gbs["rp"].Layout()
        self.panel["rp"].SetupScrolling()
        ##### end of setting up recording panel interface -----

        ### set up menu
        menuBar = wx.MenuBar()
        fileRenMenu = wx.Menu()
        quit = fileRenMenu.Append(
                            wx.Window.NewControlId(),
                            item="Quit\tCTRL+Q",
                                 )
        menuBar.Append(fileRenMenu, "&pyCamRec")
        self.SetMenuBar(menuBar)

        ### set up hot keys
        idQuit = wx.Window.NewControlId()
        self.Bind(wx.EVT_MENU, self.onClose, id=idQuit)
        accel_tbl = wx.AcceleratorTable([
                                    (wx.ACCEL_CMD,  ord('Q'), idQuit),
                                        ])
        self.SetAcceleratorTable(accel_tbl)

        ### set up status-bar
        self.statusbar = self.CreateStatusBar(1)
        self.sbBgCol = self.statusbar.GetBackgroundColour()
        self.timer["sbTimer"] = None

        updateFrameSize(self, wSz)
        self.Bind(wx.EVT_CLOSE, self.onClose)
    
    #-------------------------------------------------------------------

    def setPanelInfo(self):
        """ Set up panel information.
        
        Args:
            None
        
        Returns:
            pi (dict): Panel information.
        """
        if DEBUG: print("CamRecFrame.setPanelInfo()")
        
        wSz = self.wSz # window size
        pi = {} # panel information to return
        # top panel for UI
        pi["ui"] = dict(pos=(0, 0),
                        sz=(int(wSz[0]*0.25), wSz[1]),
                        bgCol="#cccccc",
                        style=wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER)
        uiSz = pi["ui"]["sz"]
        # panel for showing recorded image
        w = wSz[0] - uiSz[0]
        h = int(w / 1.333)
        pi["rp"] = dict(pos=(uiSz[0], 0),
                        sz=(w, h),
                        bgCol="#333333",
                        style=wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER)
        return pi
    
    #-------------------------------------------------------------------

    def onButtonPressDown(self, event, flag=''):
        """ wx.Butotn was pressed.
        
        Args:
            event (wx.Event)
            flag (str, optional): Specifying intended operation of
              the function call.
        
        Returns:
            None
        """
        if DEBUG: print("CamRecFrame.onButtonPressDown()")

        objName = ''
        if flag == '':
            obj = event.GetEventObject()
            objName = obj.GetName()
        if not obj.IsEnabled(): return

        if objName in ["addCam_btn", "remCam_btn"]:
            cho = wx.FindWindowByName("camIdx_cho", self.panel["ui"])
            choStr = cho.GetString(cho.GetSelection()).strip()
            if choStr != "":
                ci = int(choStr)
                flag = objName[:3] # add or rem
                self.addRemCam(ci, flag) # toggle selected cam

        elif objName == "remAllCam_btn":
            self.addRemCam(-1, "remAll") # remove all added cams

        elif objName == "toggleRec_btn":
            self.toggleRec() # toggle recording
    
    #-------------------------------------------------------------------

    def onChoice(self, event):
        """ wx.Choice was changed.
        
        Args: event (wx.Event)
        
        Returns: None
        """
        if DEBUG: print("CamRecFrame.onChoice()")

        obj = event.GetEventObject()
        objName = obj.GetName()
        objVal = obj.GetString(obj.GetSelection()) # text of chosen option

        if objName == "camIdx_cho":
        # cam index was chosen
            ### prepare preview image
            w = int(self.pi["ui"]["sz"][0] * 0.95)
            h = int(w/1.333)
            if objVal.strip() == "":
                ci = -1
                f = np.zeros((h,w,3), dtype=np.uint8)
            else:
                ci = int(objVal)
                f = self.cams[ci].initFrame # initial frame of the selected Cam
                f = cv2.resize(f, (w,h)) # resize to show it in UI
            ### show image
            f = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
            img = wx.Image(w, h)
            img.SetData(f.tostring())
            self.preview_sBmp.SetBitmap(img.ConvertToBitmap())
            ### enable/disable widgets related to Cam setup
            if ci in self.oCIdx:
                self.enableDisableCamWidgets(flag="add")
            else:
                self.enableDisableCamWidgets(flag="rem")

        elif objName == "outputFormat_cho":
            if objVal == "video": val = True
            elif objVal == "image": val = False
            w = wx.FindWindowByName("videoFPSlimit_spin", self.panel["ui"])
            w.Enable(val)
            w = wx.FindWindowByName("ssIntv_spin", self.panel["ui"])
            w.Enable(not val)
    
    #-------------------------------------------------------------------

    def enableDisableCamWidgets(self, flag="add"):
        """ Enable/disable some widgets related to Cam setup,
        
        Args:
            flag (str): 'add' or 'rem' (for currently selected Cam)
        
        Returns:
            None
        """
        if DEBUG: print("CamRecFrame.enableDisableCamWidgets()")

        if flag == "add": val = False
        elif flag == "rem": val = True
        addBtn = wx.FindWindowByName("addCam_btn", self.panel["ui"])
        remBtn = wx.FindWindowByName("remCam_btn", self.panel["ui"])
        ofCho = wx.FindWindowByName("outputFormat_cho", self.panel["ui"])
        vFPSSpin = wx.FindWindowByName("videoFPSlimit_spin", self.panel["ui"])
        ssIntvSpin = wx.FindWindowByName("ssIntv_spin", self.panel["ui"])
        addBtn.Enable(val) # add button
        remBtn.Enable(not val) # remove button
        ofCho.Enable(val) # output format (Choice widget)
        if flag == "add":
            vVal = False
            iVal = vVal
        else:
            outputFormat = ofCho.GetString(ofCho.GetSelection())
            if outputFormat == "video": vVal = True
            elif outputFormat == "image": vVal = False
            iVal = not vVal
        vFPSSpin.Enable(vVal) # video FPS (SpinCtrl widget)
        ssIntvSpin.Enable(iVal) # image snapshot interval (SpinCtrl widget)

        ### enable/disable recording button depending on
        ###   whether there's any added Cam in self.oCIdx
        btn = wx.FindWindowByName("toggleRec_btn", self.panel["ui"])
        if len(self.oCIdx) == 0: btn.Disable()
        else: btn.Enable()
    
    #-------------------------------------------------------------------

    def stopAllTimers(self):
        """ Stop all running timers
        
        Args: None
        
        Returns: None
        """
        if DEBUG: print("CamRecFrame.stopAllTimers()")

        for k in self.timer.keys():
            if self.timer[k] != None:
                try: self.timer[k].Stop()
                except: pass
    
    #-------------------------------------------------------------------

    def onTimer(self, event, flag):
        """ Processing on wx.EVT_TIMER event
        
        Args:
            event (wx.Event)
            flag (str): Key (name) of timer
        
        Returns:
            None
        """
        if DEBUG: print("CamRecFrame.onTimer()")

        if flag == "rDur": # recording duration timer
            if self.rSTime != -1:
                e_time = time() - self.rSTime
                timeStr = str(timedelta(seconds=e_time)).split('.')[0]
                self.rDur_sTxt.SetLabel(timeStr)
    
    #-------------------------------------------------------------------

    def toggleRec(self):
        """ Toggle cam recording.
        
        Args: None
        
        Returns: None
        """
        if DEBUG: print("CamRecFrame.toggleRec()")

        ### if it doesn't exist yet, set up recording duration timer
        if not "rDur" in self.timer.keys():
            self.timer["rDur"] = wx.Timer(self)
            self.Bind(wx.EVT_TIMER,
                      lambda event: self.onTimer(event, "rDur"),
                      self.timer["rDur"])

        recBtn = wx.FindWindowByName("toggleRec_btn", self.panel["ui"])
        if self.is_recording:
            ### stop recording
            self.timer["rDur"].Stop()
            for q2t in self.q2t: q2t.put('rec_stop', True, None)
            self.rSTime = -1
            self.rDur_sTxt.SetLabel('0:00:00')
            recBtn.SetLabel("start Recording")
            flag = True

        else:
            ### start recording
            self.rSTime = time()
            self.timer["rDur"].Start(1000)
            for q2t in self.q2t: q2t.put('rec_init', True, None)
            recBtn.SetLabel("Stop")
            flag = False

        btn = wx.FindWindowByName("addCam_btn", self.panel["ui"])
        btn.Enable(flag)
        btn = wx.FindWindowByName("remCam_btn", self.panel["ui"])
        btn.Enable(flag)
        
        self.is_recording = not self.is_recording
    
    #-------------------------------------------------------------------

    def toggleCamThread(self, ci):
        """ Start/Stop a cam thread
        
        Args:
            ci (int): Index of cam to start
        
        Returns:
            None
        """
        if DEBUG: print("CamRecFrame.startCamThread()")

        if self.th[ci] == -1: # thread is not running
            ### update output format for Cam recording
            cho = wx.FindWindowByName("outputFormat_cho", self.panel["ui"])
            outputFormat = cho.GetString(cho.GetSelection()) # video or image
            self.cams[ci].outputFormat = outputFormat
            if outputFormat == "video":
                ### update FPS limit for Cam recording
                w = wx.FindWindowByName("videoFPSlimit_spin", self.panel["ui"])
                fpsLimit = str2num(w.GetValue(), 'float')
                if fpsLimit != None: self.cams[ci].fpsLimit = fpsLimit
            elif outputFormat == "image":
                ### update snapshot interval for Cam recording
                w = wx.FindWindowByName("ssIntv_spin", self.panel["ui"])
                ssIntv = str2num(w.GetValue(), 'float')
                if ssIntv != None: self.cams[ci].ssIntv = ssIntv
            ### start Cam thread
            args = (self.q2m, self.q2t[ci], self.recFolder,)
            self.th[ci] = Thread(target=self.cams[ci].run, args=args)
            self.th[ci].start()
            ### start timer to check q2m
            ###   (queued message from the running thread)
            if "chkQ2M" in self.timer.keys() and \
              self.timer["chkQ2M"].IsRunning() == False:
                self.timer["chkQ2M"].Start(50)
            else:
                self.timer["chkQ2M"] = wx.Timer(self)
                self.Bind(wx.EVT_TIMER, self.chkQ2M, self.timer["chkQ2M"])
                self.timer["chkQ2M"].Start(50)
            # log message
            log = "%s, Cam-%.2i thread started\n"%(get_time_stamp(), ci)

        else:
            ### stop Cam thread
            self.q2t[ci].put("quit", True, None) # send message to quit thread
            self.th[ci].join()
            self.th[ci] = -1
            ### if no cam thread is running, stop chkQ2M timer as well.
            if self.th == [-1]*len(self.th):
                self.timer["chkQ2M"].Stop()
            # log message
            log = "%s, Cam-%.2i thread stopped\n"%(get_time_stamp(), ci)
        writeFile(self.logFile, log)
    
    #-------------------------------------------------------------------

    def addRemCam(self, ci=-1, flag="add"):
        """ Add/Remove a cam
        
        Args:
            ci (int): Index of cam
            flag (str): Flag for turning on (add) or off (rem)
        
        Returns:
            None
        """
        if DEBUG: print("CamRecFrame.toggleCam()")

        if flag == "add" and ci != -1:
            if self.th[ci] == -1:
                self.toggleCamThread(ci)
                self.oCIdx.append(ci)
        elif flag == "rem" and ci != -1:
            if self.th[ci] != -1:
                self.toggleCamThread(ci)
                self.oCIdx.remove(ci)
        elif flag == "remAll":
            for ci in list(self.oCIdx):
                if self.th[ci] != -1:
                    self.toggleCamThread(ci)
                    self.oCIdx.remove(ci)
        self.enableDisableCamWidgets(flag=flag[:3])

        ### show opened cam index and its recording type
        sTxt = wx.FindWindowByName("openCI_sTxt", self.panel["ui"])
        s = []
        for ci in self.oCIdx:
            of = self.cams[ci].outputFormat[0] # first letter of output format
            if of == "v": # output format is video
                w = wx.FindWindowByName("videoFPSlimit_spin", self.panel["ui"])
            elif of == "i": # output format is image
                w = wx.FindWindowByName("ssIntv_spin", self.panel["ui"])
            of += "/%s"%(w.GetValue())
            s.append("%i[%s]"%(ci, of))
        sTxt.SetLabel(str(s).strip("[]").replace("'",""))

        pSz = self.pi["rp"]["sz"] # panel size
        # number of frames on one side
        self.nCOnSide = int(np.ceil(np.sqrt(len(self.oCIdx))))
        ### update display frame size for each cam
        if self.nCOnSide == 0:
            w, h = pSz
        else:
            w = int(pSz[0]/self.nCOnSide)
            h = int(w/1.333)
        self.dispCSz = [w, h]
        ### init display image with black
        self.dispArr[:,:,:] = 0
        img = wx.Image(self.dispCSz[0], self.dispCSz[1])
        self.disp_sBmp.SetBitmap(img.ConvertToBitmap())
    
    #-------------------------------------------------------------------

    def chkQ2M(self, event):
        """ Check queue to main, q2m, to receive queued messages from threads
        
        Args: event (wx.Event)
        
        Returns: None
        """
        #if DEBUG: print("CamRecFrame.chkQ2M()")

        ### get (last) messages from each Cam's queue
        qData = [None] * len(self.th)
        while self.q2m.empty() == False:
            try:
                cIdx, frame = self.q2m.get(False)
                qData[cIdx] = frame
            except: pass

        ### combin frame images from didfferent cams
        ###   to a single array, self.dispArr.
        cw, ch = self.dispCSz
        oci = 0 # index for self.oCIdx
        for ri in range(self.nCOnSide): # row
            for ci in range(self.nCOnSide): # column
                if oci >= len(self.oCIdx): break
                cIdx = self.oCIdx[oci] # cam index
                oci += 1
                if not isinstance(qData[cIdx], np.ndarray): continue
                f = qData[cIdx] # frame
                # resize to display
                f = cv2.resize(f, tuple(self.dispCSz))
                ### set queued frame data into display array
                x = cw*ci
                y = ch*ri
                self.dispArr[y:y+ch, x:x+cw, :] = f
                cv2.putText(self.dispArr, # image
                            "Cam-%.2i"%(cIdx), # string
                            (x+5, y+20), # bottom-left
                            cv2.FONT_HERSHEY_PLAIN, # fontFace
                            1.0, # fontScale
                            (0,127,255), # color
                            1) # thickness

        ### display combined frame image on app
        dispFrame = cv2.cvtColor(self.dispArr, cv2.COLOR_BGR2RGB)
        img = wx.Image(self.pi["rp"]["sz"][0], self.pi["rp"]["sz"][1])
        img.SetData(dispFrame.tostring())
        self.disp_sBmp.SetBitmap(img.ConvertToBitmap())
    
    #-------------------------------------------------------------------

    def onClose(self, event):
        """ Close this frame.
        
        Args: event (wx.Event)
        
        Returns: None
        """
        if DEBUG: print("CamRecFrame.onClose()")

        self.stopAllTimers()
        ### stop any running Cam thread
        for ci in range(len(self.th)):
            if self.th[ci] != -1: self.toggleCamThread(ci)
            self.cams[ci].close()
        wx.CallLater(500, self.Destroy)
    
    #-------------------------------------------------------------------

#=======================================================================

class CamRecApp(wx.App):
    def OnInit(self):
        self.frame = CamRecFrame()
        self.frame.Show()
        self.SetTopWindow(self.frame)
        return True
    
#=======================================================================

if __name__ == '__main__':
    if len(argv) > 1:
        if argv[1] == '-w': GNU_notice(1)
        elif argv[1] == '-c': GNU_notice(2)
    else:
        GNU_notice(0)
        app = CamRecApp(redirect = False)
        app.MainLoop()
