import asyncio
from pynput.keyboard import Listener
from mocap_api import *

class MCPBase:
    def __init__(self):
        # Initialize current command and running command status
        self.current_command = -1  # Current command being executed
        self.capture_key = False  # Capture status flag
        self.connent_key = False  # Connection status flag
        self.app = MCPApplication()  # Create application instance
        settings = MCPSettings()  # Create settings instance
        
        # Configure BVH data format to binary
        settings.set_bvh_data(MCPBvhData.Binary)
        # Enable BVH data transformation
        settings.set_bvh_transformation(MCPBvhDisplacement.Enable)
        # Set rotation order to YZX
        settings.set_bvh_rotation(MCPBvhRotation.YXZ)
        # Configure UDP data transmission address and port
        settings.SetSettingsUDPEx('10.42.0.101', 8002)
        settings.SetSettingsUDPServer('10.42.0.202', 8080)
        
        # Apply configuration to application instance and open connection
        self.app.set_settings(settings)
        self.app.open()

    def get_current_command_title(self):
        # Return the title corresponding to the current command
        if self.current_command == EMCPCommand.CommandStartCapture:
            return 'Start Capture'
        elif self.current_command == EMCPCommand.CommandStopCapture:
            return 'Stop Capture'
        elif self.current_command == EMCPCommand.CommandCalibrateMotion:
            return 'Calibrate Motion'
        elif self.current_command == EMCPCommand.CommandResumeOriginalHandsPosture:
            return 'Resume Hands'
        elif self.current_command == EMCPCommand.CommandClearZeroMotionDrift:
            return 'Reset 0 Motion Drift'
        elif self.current_command == EMCPCommand.CommandResumeOriginalPosture:
            return 'Resume Body'
        elif self.current_command == EMCPCommand.CommandZeroPosition:
            return 'Zero Position'
        else:
            return 'None'

    def check_current_command(self, running_command):
        # Check if the specified command can be run
        if self.connent_key == False:
            print('Link failure.')  # Print error message if not connected
            return False
        elif self.current_command != -1:
            # If another command is running, prohibit executing other commands
            print(f'Pending command {self.get_current_command_title()} is running.')
            return False
        # Commands other than start capture need capture to be started first
        elif self.capture_key == False and running_command != EMCPCommand.CommandStartCapture:
            print('Please start capture command first.')
            return False
        return True

    def running_command(self, running_command):
        # Execute the specified command
        if self.check_current_command(running_command) == True:            
            self.app.queue_command(running_command)  # Execute command
            self.current_command = running_command  # Update current command
            print(f'Pending command {self.get_current_command_title()} is running.')

    def handleNotify(self, notifyData):
        # Handle notification events
        if notifyData._notify == MCPEventNotify.Notify_SystemUpdated:
            mcpSystem = MCPSystem(notifyData._notifyHandle)  # Get system information
            print(f'MasterInfo : ( Version : {mcpSystem.get_master_version()}, SerialNumber : {mcpSystem.get_master_serial_number()} )')

    def handleResult(self, commandRespond):
        # Handle command results
        command = MCPCommand()
        _commandHandle = commandRespond._commandHandle
        ret_code = command.get_result_code(_commandHandle)
        if ret_code != 0:
            ret_msg = command.get_result_message(_commandHandle)
            print(f'ResultCode: {self.get_current_command_title()}, ResultMessage: {ret_msg}')  # Print command execution error message
        else:
            print(f'{self.get_current_command_title()} done.')  # Print command execution success message
            if self.current_command == EMCPCommand.CommandStopCapture:
                self.capture_key = False
        command.destroy_command(_commandHandle)  # Destroy command handle
        self.current_command = -1  # Reset current command

    def handleRunning(self, commandRespond):
        # Handle calibration progress
        _calibrateProgressHandle = MCPCommand().get_progress(commandRespond._commandHandle)
        progressHandle = MCPCalibrateMotionProgress(_calibrateProgressHandle)
        count = progressHandle.get_count_of_support_poses()

        str_poses = "Support poses:"
        for i in range(count):
            name = progressHandle.get_name_of_support_poses(i)
            str_poses += name
            if i + 1 != count:
                str_poses += ", "
        str_poses += " : "     
        result_progress = 0
        # Get calibration step and calibration name
        result_current_step, result_p_name = progressHandle.get_step_current_pose()
        if result_current_step == MCPCalibrateMotionProgressStep.CalibrateMotionProgressStep_Countdown:
            # Get calibration countdown
            result_countdown, result_p_name = progressHandle.get_countdown_current_pose()
            str_poses += (f"Calibration-({result_p_name})-Countdown {result_countdown}.")
        elif result_current_step == MCPCalibrateMotionProgressStep.CalibrateMotionProgressStep_Progress:
            # Get calibration progress
            result_progress, result_p_name = progressHandle.get_progress_current_pose()
            str_poses += (f"Calibration-({result_p_name})-Progress {result_progress}.")

        elif result_current_step == MCPCalibrateMotionProgressStep.CalibrateMotionProgressStep_Prepare:
            str_poses += (f"Calibration-({result_p_name}) is preparing.")
        else:
            str_poses += (f'Calibration-Unknown({result_current_step}) is running.')

        print(str_poses) 

        if result_progress == 100:
            print('Waiting for the completion of the calibration of human posture command execution')   

    async def update(self):
        try: 
            # Asynchronous update function to handle event loop
            while True:
                evts = self.app.poll_next_event()  # Get next event
                for evt in evts:
                    self.connent_key = True
                    if evt.event_type == MCPEventType.AvatarUpdated:
                        if self.current_command != EMCPCommand.CommandCalibrateMotion and self.current_command == -1:
                            self.capture_key = True
                            self.handleAvatar(evt.event_data.avatar_handle)
                    elif evt.event_type == MCPEventType.Notify:
                        self.handleNotify(evt.event_data.notifyData)
                    elif evt.event_type == MCPEventType.CommandReply:
                        if evt.event_data.commandRespond._replay == MCPReplay.MCPReplay_Response:
                            print('MCPReplay_Response')
                        elif evt.event_data.commandRespond._replay == MCPReplay.MCPReplay_Running:
                            self.handleRunning(evt.event_data.commandRespond)
                        elif evt.event_data.commandRespond._replay == MCPReplay.MCPReplay_Result:
                            self.handleResult(evt.event_data.commandRespond)
                    elif evt.event_type == MCPEventType.RigidBodyUpdated:
                        print('rigid body updated')
                await asyncio.sleep(0.1)  # Wait for 0.1 seconds
        except Exception as e:
            print(f"An error occurred: {e}")    

    async def main_async(self):
        # Main asynchronous function
        main = self
        loop = asyncio.get_event_loop()

        # Keyboard event handler function
        def on_key_press(key):
            try:
                key_name = key.char.lower()
                print(f"Key pressed: {key_name}")
                if key_name == 'n':
                    main.running_command(EMCPCommand.CommandStartCapture)
                elif key_name == 'f':
                    main.running_command(EMCPCommand.CommandStopCapture)
                elif key_name == 'c':
                    main.running_command(EMCPCommand.CommandCalibrateMotion)
                elif key_name == 'r':
                    main.running_command(EMCPCommand.CommandResumeOriginalHandsPosture)     
                elif key_name == '0':
                    main.running_command(EMCPCommand.CommandClearZeroMotionDrift)     
                elif key_name == 'o':
                    main.running_command(EMCPCommand.CommandResumeOriginalPosture)     
                elif key_name == 'z':
                    main.running_command(EMCPCommand.CommandZeroPosition)     
            except AttributeError:
                if key == key.esc:
                    print("ESC key pressed, exiting program")
                    return False  # Exit listener

        # Start keyboard listener
        with Listener(on_press=on_key_press) as listener:
            asyncio.run_coroutine_threadsafe(main.update(), loop)  # Start event update
            print("Press N to Start Capture,  C to calibrate, R to Resume Hands, 0 to Reset 0 Motion Drift, O to Resume Body, Z ti Zero Position, F to Stop Capture,press ESC to exit program")
            await loop.run_in_executor(None, listener.join)  # Wait for listener to exit