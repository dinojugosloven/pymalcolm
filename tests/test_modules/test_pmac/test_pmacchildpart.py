import numpy as np
import pytest
from mock import Mock, call, patch
from scanpointgenerator import LineGenerator, CompoundGenerator

from malcolm.core import Context, Process
from malcolm.modules.pmac.parts import PmacChildPart
from malcolm.testutil import ChildTestCase
from malcolm.yamlutil import make_block_creator

SHOW_GRAPHS = False
# Uncomment this to show graphs when running under PyCharm
# SHOW_GRAPHS = "PYCHARM_HOSTED" in os.environ


class TestPMACChildPart(ChildTestCase):
    def setUp(self):
        self.process = Process("Process")
        self.context = Context(self.process)
        pmac_block = make_block_creator(
            __file__, "test_pmac_manager_block.yaml")
        self.child = self.create_child_block(
            pmac_block, self.process, mri_prefix="PMAC",
            config_dir="/tmp")
        # These are the child blocks we are interested in
        self.child_x = self.process.get_controller("BL45P-ML-STAGE-01:X")
        self.child_y = self.process.get_controller("BL45P-ML-STAGE-01:Y")
        self.child_cs1 = self.process.get_controller("PMAC:CS1")
        self.child_traj = self.process.get_controller("PMAC:TRAJ")
        self.child_status = self.process.get_controller("PMAC:STATUS")
        # Set some static vars
        self.set_attributes(self.child_cs1, port="CS1")
        self.o = PmacChildPart(name="pmac", mri="PMAC")
        self.context.set_notify_dispatch_request(self.o.notify_dispatch_request)
        self.process.start()
        self.set_attributes(self.child, outputTriggers=True)

    def tearDown(self):
        del self.context
        self.process.stop(timeout=1)

    def _______________test_bad_units(self):
        with self.assertRaises(AssertionError) as cm:
            self.do_configure(["x", "y"], units="m")
        assert str(cm.exception) == "x: Expected scan units of 'm', got 'mm'"

    def resolutions_and_use_call(self, useB=True):
        return [
            call.put('useA', True),
            call.put('useB', useB),
            call.put('useC', False),
            call.put('useU', False),
            call.put('useV', False),
            call.put('useW', False),
            call.put('useX', False),
            call.put('useY', False),
            call.put('useZ', False)]

    def set_motor_attributes(
            self, x_pos=0.5, y_pos=0.0, units="mm",
            x_acceleration=2.5, y_acceleration=2.5,
            x_velocity=1.0, y_velocity=1.0):
        # create some parts to mock the motion controller and 2 axes in a CS
        self.set_attributes(
            self.child_x, cs="CS1,A",
            accelerationTime=x_velocity/x_acceleration, resolution=0.001,
            offset=0.0, maxVelocity=x_velocity, readback=x_pos,
            velocitySettle=0.0, units=units)
        self.set_attributes(
            self.child_y, cs="CS1,B",
            accelerationTime=y_velocity/y_acceleration, resolution=0.001,
            offset=0.0, maxVelocity=y_velocity, readback=y_pos,
            velocitySettle=0.0, units=units)

    def do_configure(self, axes_to_scan, completed_steps=0, x_pos=0.5,
                     y_pos=0.0, duration=1.0, units="mm"):
        self.set_motor_attributes(x_pos, y_pos, units)
        steps_to_do = 3 * len(axes_to_scan)
        xs = LineGenerator("x", "mm", 0.0, 0.5, 3, alternate=True)
        ys = LineGenerator("y", "mm", 0.0, 0.1, 2)
        generator = CompoundGenerator([ys, xs], [], [], duration)
        generator.prepare()
        self.o.configure(
            self.context, completed_steps, steps_to_do, {},
            generator, axes_to_scan)

    def test_validate(self):
        generator = CompoundGenerator([], [], [], 0.0102)
        axesToMove = ["x"]
        # servoFrequency() return value
        self.child.handled_requests.post.return_value = 4919.300698316487
        ret = self.o.validate(self.context, generator, axesToMove)
        expected = 0.010166
        assert ret.value.duration == expected

    @patch("malcolm.modules.pmac.parts.pmacchildpart.INTERPOLATE_INTERVAL",
           0.2)
    def test_configure(self):
        self.do_configure(axes_to_scan=["x", "y"])
        assert self.child.handled_requests.mock_calls == [
            call.post('writeProfile',
                      csPort='CS1', timeArray=[0.002], userPrograms=[8]),
            call.post('executeProfile'),
            call.post('moveCS1', a=-0.1375, b=0.0, moveTime=1.0375),
            # pytest.approx to allow sensible compare with numpy arrays
            call.post('writeProfile',
                      csPort='CS1',
                      a=pytest.approx([
                       -0.125, 0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.6375,
                       0.625, 0.5, 0.375, 0.25, 0.125, 0.0, -0.125, -0.1375]),
                      b=pytest.approx([
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.05,
                       0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]),
                      timeArray=pytest.approx([
                       100000, 500000, 500000, 500000, 500000, 500000, 500000,
                       200000, 200000, 500000, 500000, 500000, 500000, 500000,
                       500000, 100000]),
                      userPrograms=pytest.approx([
                       1, 4, 1, 4, 1, 4, 2, 8, 1, 4, 1, 4, 1, 4, 2, 8]),
                      velocityMode=pytest.approx([
                       2, 0, 0, 0, 0, 0, 1, 0, 2, 0, 0, 0, 0, 0, 1, 3])
                      )
            ]
        assert self.o.completed_steps_lookup == [
            0, 0, 1, 1, 2, 2, 3, 3,
            3, 3, 4, 4, 5, 5, 6, 6]

    @patch("malcolm.modules.pmac.parts.pmactrajectorypart.PROFILE_POINTS", 4)
    @patch("malcolm.modules.pmac.parts.pmactrajectorypart.INTERPOLATE_INTERVAL",
           0.2)
    def test_update_step(self):
        self.do_configure(axes_to_scan=["x", "y"], x_pos=0.0, y_pos=0.2)
        positionsA = self.child.handled_requests.put.call_args_list[-5][0][1]
        assert len(positionsA) == 4
        assert positionsA[-1] == 0.25
        assert self.o.end_index == 2
        assert len(self.o.completed_steps_lookup) == 5
        assert len(self.o.profile["time_array"]) == 1
        self.o.registrar = Mock()
        self.child.handled_requests.reset_mock()
        self.o.update_step(
            3, self.context.block_view("PMAC:TRAJ"))
        self.o.registrar.report.assert_called_once()
        assert self.o.registrar.report.call_args[0][0].steps == 1
        assert not self.o.loading
        assert self.child.handled_requests.mock_calls == [
            call.put('pointsToBuild', 4),
            call.put('positionsA', pytest.approx([
                0.375, 0.5, 0.625, 0.6375])),
            call.put('positionsB', pytest.approx([
                0.0, 0.0, 0.0, 0.05])),
            call.put('timeArray', pytest.approx([
                500000, 500000, 500000, 200000])),
            call.put('userPrograms', pytest.approx([
                1, 4, 2, 8])),
            call.put('velocityMode', pytest.approx([
                0, 0, 1, 0])),
            call.post('appendProfile')]
        assert self.o.end_index == 3
        assert len(self.o.completed_steps_lookup) == 9
        assert len(self.o.profile["time_array"]) == 1

    def test_run(self):
        self.o.run(self.context)
        assert self.child.handled_requests.mock_calls == [
            call.post('executeProfile'),
            call.when_values_matches('pointsScanned', 0, None, 0.1, None)]

    def test_reset(self):
        self.o.reset(self.context)
        assert self.child.handled_requests.mock_calls == [
            call.post('abortProfile')]

    def test_multi_run(self):
        self.do_configure(axes_to_scan=["x"])
        assert self.o.completed_steps_lookup == (
            [0, 0, 1, 1, 2, 2, 3, 3])
        self.child.handled_requests.reset_mock()
        self.do_configure(
            axes_to_scan=["x"], completed_steps=3, x_pos=0.6375)
        assert self.child.handled_requests.mock_calls == [
            call.put('numPoints', 4000000),
            call.put('cs', 'CS1'),
            call.put('useA', False),
            call.put('useB', False),
            call.put('useC', False),
            call.put('useU', False),
            call.put('useV', False),
            call.put('useW', False),
            call.put('useX', False),
            call.put('useY', False),
            call.put('useZ', False),
            call.put('pointsToBuild', 1),
            call.put('timeArray', pytest.approx([2000])),
            call.put('userPrograms', pytest.approx([8])),
            call.put('velocityMode', pytest.approx([3])),
            call.post('buildProfile'),
            call.post('executeProfile'),
        ] + self.resolutions_and_use_call(useB=False) + [
                   call.put('pointsToBuild', 8),
                   call.put('positionsA', pytest.approx([
                       0.625, 0.5, 0.375, 0.25, 0.125, 0.0, -0.125, -0.1375])),
                   call.put('timeArray', pytest.approx([
                       100000, 500000, 500000, 500000, 500000, 500000, 500000,
                       100000])),
                   call.put('userPrograms',
                            pytest.approx([1, 4, 1, 4, 1, 4, 2, 8])),
                   call.put('velocityMode',
                            pytest.approx([2, 0, 0, 0, 0, 0, 1, 3])),
                   call.post('buildProfile')
               ]

    @patch("malcolm.modules.pmac.parts.pmactrajectorypart.INTERPOLATE_INTERVAL",
           0.2)
    def test_long_steps_lookup(self):
        self.do_configure(
            axes_to_scan=["x"], completed_steps=3, x_pos=0.62506, duration=14.0)
        assert self.child.handled_requests.mock_calls[-6:] == [
            call.put('pointsToBuild', 14),
            call.put('positionsA', pytest.approx([
                0.625, 0.5625, 0.5, 0.4375, 0.375, 0.3125, 0.25, 0.1875,
                0.125, 0.0625, 0.0, -0.0625, -0.125, -0.12506377551020409])),
            call.put('timeArray', pytest.approx([
                7143, 3500000, 3500000, 3500000, 3500000, 3500000, 3500000,
                3500000, 3500000, 3500000, 3500000, 3500000, 3500000, 7143])),
            call.put('userPrograms', pytest.approx([
                1, 0, 4, 0, 1, 0, 4, 0, 1, 0, 4, 0, 2, 8])),
            call.put('velocityMode', pytest.approx([
                2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 3])),
            call.post('buildProfile')
        ]
        assert self.o.completed_steps_lookup == (
            [3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6])

    @patch("malcolm.modules.pmac.parts.pmactrajectorypart.PROFILE_POINTS", 9)
    def test_split_in_a_long_step_lookup(self):
        self.do_configure(
            axes_to_scan=["x"], completed_steps=3, x_pos=0.62506,
            duration=14.0)
        # The last 6 calls show what trajectory we are building, ignore the
        # first 11 which are just the useX calls and cs selection
        assert self.child.handled_requests.mock_calls[-6:] == [
            call.put('pointsToBuild', 9),
            call.put('positionsA', pytest.approx([
                0.625, 0.5625, 0.5, 0.4375, 0.375, 0.3125, 0.25, 0.1875,
                0.125])),
            call.put('timeArray', pytest.approx([
                7143, 3500000, 3500000, 3500000, 3500000, 3500000, 3500000,
                3500000, 3500000])),
            call.put('userPrograms', pytest.approx([
                1, 0, 4, 0, 1, 0, 4, 0, 1])),
            call.put('velocityMode', pytest.approx([
                2, 0, 0, 0, 0, 0, 0, 0, 0])),
            call.post('buildProfile')
        ]
        # The completed steps works on complete (not split) steps, so we expect
        # the last value to be the end of step 6, even though it doesn't
        # actually appear in the velocity arrays
        assert self.o.completed_steps_lookup == (
            [3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6])
        # Mock out the registrar that would have been registered when we
        # attached to a controller
        self.o.registrar = Mock()
        # Now call update step and get it to generate the next lot of points
        # scanned can be any index into completed_steps_lookup so that there
        # are less than PROFILE_POINTS left to go in it
        self.o.update_step(
            scanned=2, child=self.process.block_view("PMAC:TRAJ"))
        # Expect the rest of the points
        assert self.child.handled_requests.mock_calls[-6:] == [
            call.put('pointsToBuild', 5),
            call.put('positionsA', pytest.approx([
                0.0625, 0.0, -0.0625, -0.125, -0.12506377551020409])),
            call.put('timeArray', pytest.approx([
                3500000, 3500000, 3500000, 3500000, 7143])),
            call.put('userPrograms', pytest.approx([
                0, 4, 0, 2, 8])),
            call.put('velocityMode', pytest.approx([
                0, 0, 0, 1, 3])),
            call.post('appendProfile')
        ]
        assert self.o.registrar.report.call_count == 1
        assert self.o.registrar.report.call_args[0][0].steps == 3
        # And for the rest of the lookup table to be added
        assert self.o.completed_steps_lookup == (
            [3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6])

    def turnaround_overshoot(
            self, go_really_fast=False, title='', points=30):
        """ check for a previous bug in a sawtooth X,Y scan
        The issue was that the first point at the start of each rising edge
        overshot in Y. The parameters for each rising edge are below.

        Line Y, start=-2.5, stop= -2.5 +0.025, points=30
        Line X, start=-0.95, stop= -0.95 +0.025, points=30
        duration=0.15

        X motor: VMAX=17, ACCL=0.1 (time to VMAX)
        Y motor: VMAX=1, ACCL=0.2
        """
        x = -2.5
        y = -.95
        p = points  # set to 30 for Tom's original numbers
        d = .025 * p / 30
        xs = LineGenerator("x", "mm", x, x + d, p)
        ys = LineGenerator("y", "mm", y, y + d, p)
        # Toms original parameters below
        # xs = LineGenerator("x", "mm", -2.5, -2.475, 30)
        # ys = LineGenerator("y", "mm", -0.95, -0.925, 30)

        generator = CompoundGenerator([ys, xs], [], [], 0.15)
        generator.prepare()

        if go_really_fast:
            motion_parts = self.set_motor_attributes(
                x_acceleration=17.0 / 0.1, y_acceleration=1. / 0.2,
                x_velocity=17, y_velocity=1,
                x_pos=-2.5, y_pos=-.95)
        else:
            motion_parts = self.set_motor_attributes(
                x_acceleration=1. / 0.1, y_acceleration=1. / 0.2,
                x_velocity=17, y_velocity=1,
                x_pos=-2.5, y_pos=-.95)

        self.o.configure(self.context, 0, p * 2, motion_parts, generator,
                         ["x", "y"])

        a = self.cs.attributes
        # add in the start point to the position and time arrays
        xp = np.array([a['demandA']])
        yp = np.array([a['demandB']])
        tp = np.array([0])
        for c in self.child.handled_requests.mock_calls:
            if c[1][0] == 'positionsA':
                xp = np.append(xp, (c[1][1]))
            if c[1][0] == 'positionsB':
                yp = np.append(yp, c[1][1])
            if c[1][0] == 'timeArray':
                if c[1][1].size > 1:  # reject the reset triggers call
                    tp = np.append(tp, c[1][1])
            if c[1][0] == 'pointsToBuild':
                total_points = c[1][1]

        # if this test is run in pycharm then it plots some results
        # to help diagnose issues
        if SHOW_GRAPHS:
            import matplotlib.pyplot as plt
            # plt.title("{} x/y {} points".format(title, xp.size))
            # plt.plot(xp, yp, '+', ms=2.5)
            # plt.show()

            # plt.title("{} x/point {} points".format(title, xp.size))
            # plt.plot(xp, range(xp.size), '+', ms=2.5)
            # plt.show()

            times = np.cumsum(tp / 1000)  # show in millisecs
            plt.title("{} x/time {} points".format(title, xp.size))

            plt.plot(xp, times, '+', ms=2.5)
            plt.show()

        return xp

    def test_turnaround_overshoot(self):
        x1 = self.turnaround_overshoot(
            go_really_fast=False,
            title='test_turnaround_overshoot 10 slower',
            points=30)
        self.child.handled_requests.reset_mock()
        x2 = self.turnaround_overshoot(
            go_really_fast=True,
            title='test_turnaround_overshoot 10 fast',
            points=30)
        self.child.handled_requests.reset_mock()

        # checks that the two turnarounds only contain points
        # between the first line end and the second line start
        assert x2[61] > x2[62] > x2[63], \
            "Bad turnaround point in fast profile"
        assert x1[61] > x1[62] > x1[63] > x1[64] > x1[65] > x1[66], \
            "Bad turnaround point in slow profile"
