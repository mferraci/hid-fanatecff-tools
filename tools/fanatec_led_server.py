#!/usr/bin/python3
import sys
import os
import time
import threading

sys.path.append("../dbus")
import fanatec_input

LEDS = 9

verbose = False

def set_leds(values):
    global wheel
    wheel.RPM = values


def set_display(value):
    global wheel
    wheel.Display = value


def set_pedals_rumble(abs, tc):
    global pedals
    pedals.rumble = "%i" % ((0xFF if tc else 0) << 16 | (0xFF if abs else 0) << 8)


# clear leds and display
def clear():
    set_leds([False] * 9)
    set_display(-1)


wheels_dict = {
    fanatec_input.CSL_STEERING_WHEEL_P1_V2: fanatec_input.CSLP1V2Wheel,
    fanatec_input.CSL_ELITE_STEERING_WHEEL_WRC_ID: fanatec_input.CSLP1V2Wheel,
    fanatec_input.CLUBSPORT_STEERING_WHEEL_F1_IS_ID: fanatec_input.CSLEliteWheel,
    fanatec_input.CLUBSPORT_STEERING_WHEEL_F1_ES_V2_ID: fanatec_input.CSLEliteWheel
}


class Client(threading.Thread):
    def __init__(
        self,
        ev,
        wheel,
        dbus=True,
        device=None,
        display="gear",
        verbose=False,
    ):
        threading.Thread.__init__(self)
        if not dbus and device is None:
            raise Exception("If dbus is not used, a device must be specified!")
        self.ev = ev
        self.dbus = dbus
        self.device = fanatec_input.get_device(verbose)
        self.display = display
        self.wheel = wheels_dict[wheel]
        self.rate = 10
        self._revLightsPercent = 0
        self._tcInAction = 0
        self._absInAction = 0
        self._speedKmh = 0
        self._gear = 0
        self._suggestedGear = 0
        self._verbose = verbose


#Wheel data is passed as argument. /wheel_id definition is broken in fanatec driver
        # hold wheel data
        #self.wheel = self.get_wheel_code()
    #def get_wheel_code(self):
    #     base = fanatec_input.get_sysfs_base()
    #    with open(base + "/wheel_id") as f:
    #        # convert e.g. "0x0005\n" to "0005"
    #        wheel_id = f.read().replace("\n", "")[2:]
    #    return wheels_dict[wheel_id]

    def prerun(self):
        pass

    def postrun(self):
        pass

    def tick(self):
        time.sleep(1 / self.rate)
        return True

    @staticmethod
    def rpms_to_revlights(rpms, maxrpm):
        return 100 * max(0, (rpms - 0.9 * maxrpm)) / (maxrpm - 0.9 * maxrpm)
        

    @property
    def revLightsPercent(self):
        return self._revLightsPercent

    @property
    def tcInAction(self):
        return self._tcInAction

    @property
    def absInAction(self):
        return self._absInAction

    @property
    def speedKmh(self):
        return self._speedKmh

    @property
    def gear(self):
        return self._gear

    @property
    def suggestedGear(self):
        return self._suggestedGear

    def run(self):

        while not self.ev.isSet():
            self._do_run()

    def _do_run(self):
        if self._verbose:
            print(self, 'waiting for game connection')


        self.prerun()

        if not self.dbus:
            while not self.ev.isSet():
                try:
                    fanatec_input.get_sysfs_base(self._verbose)
                except Exception as e:
                    print(e)
                    self.postrun()
                    print(self, 'finished.')
                    time.sleep(1)
                    return
                if self._verbose:
                    print("Found sysfs for device", self.device)

                try:
                    display = self.wheel.get_sysfs("display")
                    if self._verbose:
                        print(display)
                    pedals = self.wheel.get_sysfs("rumble")
                    if self._verbose:
                        print(pedals)
                    if not os.path.isfile(display):
                        display = None
                    if not os.path.isfile(pedals):
                        pedals = None
                except:
                    pass
                finally:
                    break

        if not self.ev.isSet():
            print(self, "connected")

            if rpms_maxed % 2 == 1:
                leds = [False] * 9
            else:
                leds = [i / LEDS < self.revLightsPercent for i in range(LEDS)]

            if self.dbus:
                set_leds(leds)
                set_display(eval("self.%s" % self.display))
                set_pedals_rumble(self.absInAction, self.tcInAction)
            else:
                rumble = "%i" % (
                    (0xFF if self.tcInAction else 0) << 16
                    | (0xFF if self.absInAction else 0) << 8
                )

            if display is not None:
                display_val = str(self.speedKmh)
            if self.display == "gear":
                if self.wheel == fanatec_input.CSLEliteWheel:
                    gear = {-1: "R", 0: "N"}
                elif self.wheel == fanatec_input.CSLP1V2Wheel:
                    gear = {-1: "-1", 0: "000"}
                display_val = (
                    gear[self.gear] if self.gear in gear else str(self.gear)
                )

                # print(display_val)
            open(display, "w").write(display_val)

            if pedals is not None:
                open(pedals, "w").write(str(rumble))
            self.wheel.get_sysfs_rpm()
            self.wheel.set_sysfs_rpm(self._revLightsPercent)


        self.postrun()

        print(self, "finished.")
        if not self.ev.isSet():
            self.run()


if __name__ == "__main__":
    from ac import AcClient
    from acc import AccClient
    from f1_23 import F1_23Client
    from rf2 import RF2Client
    from wrc import WrcClient
    from ams2 import AMS2Client

    import argparse
    import signal

    parser = argparse.ArgumentParser(
        description="Advanced functions for fanatec wheels with ACC"
    )
    parser.add_argument(
        "--dbus",
        action="store_true",
        help="Use dbus for communicating commands to the wheel.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Explain what is being done",
    )
    parser.add_argument(
        "--device",
        type=str,
        help="PID of the wheel (ClubSportv2 '0001', ClubSportv2.5 '0004', ...)",
        default="0005",
    )
    parser.add_argument(
        "--display",
        type=str,
        help="property that is shown on display (gear, speedKmh)",
        default="gear",
    )
    parser.add_argument(
        "--wheel",
        type=str,
        help="ID of the wheel (F1 Esport V2: 01, ClubSport P1 V2: 02, ...  )",
        default="01",
    )
    args = parser.parse_args()

    if args.dbus:
        bus = SystemBus()
        wheel = bus.get("org.fanatec.CSLElite", "/org/fanatec/CSLElite/Wheel")
        pedals = bus.get("org.fanatec.CSLElite", "/org/fanatec/CSLElite/Pedals")

    try:
        ev = threading.Event()

        def handle_sigterm(sig, frame):
            ev.set()
        signal.signal(signal.SIGTERM, handle_sigterm)

        threads = []
        for typ in [F1_23Client, AcClient, AccClient, RF2Client, WrcClient, AMS2Client]:
            threads.append(typ(ev, args.wheel, args.dbus,  args.device, args.display, args.verbose))

        for thread in threads:
            thread.start()

        # run as long as the client threads are running, or CTRL+C
        print("Running ...")

        while True:
            died = []
            for thread in threads:
                if not thread.is_alive():
                    print("Thread '%s' stopped." % thread)
                    died.append(thread)
            threads = [t for t in threads if t not in died]
            if len(threads) == 0:
                break
            time.sleep(1)

    except (KeyboardInterrupt, SystemExit):
        print("Exiting")
    except Exception as e:
        raise e
    finally:
        ev.set()
        if args.dbus:
            clear()
