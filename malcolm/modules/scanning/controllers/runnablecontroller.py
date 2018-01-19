from annotypes import Anno, Array, TYPE_CHECKING, add_call_types
from scanpointgenerator import CompoundGenerator

from malcolm.core import AbortedError, MethodModel, Queue, \
    Context, TimeoutError, AMri, NumberMeta, StringArrayMeta, Widget, \
    config_tag, Part, ABORT_TIMEOUT
from malcolm.modules.builtin.controllers import ManagerController, \
    AConfigDir, AInitialDesign, ADescription, AUseCothread, AUseGit
from ..infos import ParameterTweakInfo, RunProgressInfo, ConfigureParamsInfo
from ..util import RunnableStates, AGenerator, AAxesToMove, ConfigureParams, \
    UAxesToMove
from ..hooks import ConfigureHook, ValidateHook, PostConfigureHook, \
    RunHook, PostRunArmedHook, PostRunReadyHook, ResumeHook, ReportStatusHook, \
    AbortHook, PauseHook, SeekHook, ControllerHook

if TYPE_CHECKING:
    from typing import Dict, Tuple, List, Any, Iterable, Type, Callable

    PartContextParams = Iterable[Tuple[Part, Context, Dict[str, Any]]]
    PartConfigureParams = Dict[Part, ConfigureParamsInfo]

ss = RunnableStates

with Anno("Default value for configure() axesToMove"):
    AInitialAxesToMove = Array[str]
with Anno("The validated configure parameters"):
    AConfigureParams = ConfigureParams
with Anno("Step to mark as the last completed step, 0 for current"):
    ACompletedSteps = int


class RunnableController(ManagerController):
    """RunnableDevice implementer that also exposes GUI for child parts"""
    # The stateSet that this controller implements
    state_set = ss()

    def __init__(self,
                 mri,  # type: AMri
                 config_dir,  # type: AConfigDir
                 initial_axes_to_move=None,  # type: AInitialAxesToMove
                 initial_design="",  # type: AInitialDesign
                 description="",  # type: ADescription
                 use_cothread=True,  # type: AUseCothread
                 use_git=True,  # type: AUseGit
                 ):
        super(RunnableController, self).__init__(
            mri, config_dir, initial_design, description, use_cothread, use_git)
        # Shared contexts between Configure, Run, Pause, Seek, Resume
        self.part_contexts = {}  # type: Dict[Part, Context]
        # Any custom ConfigureParams subclasses requested by Parts
        self.part_configure_params = {}  # type: PartConfigureParams
        # Params passed to configure()
        self.configure_params = None  # type: ConfigureParams
        # This is the ConfigureParams subclass we should use in configure()
        self.configure_params_cls = ConfigureParams
        # Progress reporting dict of completed_steps for each part
        self.progress_updates = None  # type: Dict[Part, int]
        # Queue so that do_run can wait to see why it was aborted and resume if
        # needed
        self.resume_queue = None  # type: Queue
        # Queue so we can wait for aborts to complete
        self.abort_queue = None  # type: Queue
        # Stored for pause
        self.steps_per_run = 0  # type: int
        # Create sometimes writeable attribute for the current completed scan
        # step
        self.completed_steps = NumberMeta(
            "int32", "Readback of number of scan steps",
            tags=[Widget.TEXTINPUT.tag()]
        ).create_attribute_model(0)
        self.field_registry.add_attribute_model(
            "completedSteps", self.completed_steps, self.pause)
        self.set_writeable_in(self.completed_steps, ss.PAUSED, ss.ARMED)
        # Create read-only attribute for the number of configured scan steps
        self.configured_steps = NumberMeta(
            "int32", "Number of steps currently configured",
            tags=[Widget.TEXTUPDATE.tag()]
        ).create_attribute_model(0)
        self.field_registry.add_attribute_model(
            "configuredSteps", self.configured_steps)
        # Create read-only attribute for the total number scan steps
        self.total_steps = NumberMeta(
            "int32", "Readback of number of scan steps",
            tags=[Widget.TEXTUPDATE.tag()]
        ).create_attribute_model(0)
        self.field_registry.add_attribute_model("totalSteps", self.total_steps)
        # Create sometimes writeable attribute for the default axis names
        self.axes_to_move = StringArrayMeta(
            "Default axis names to scan for configure()",
            tags=[Widget.TABLE.tag(), config_tag()]
        ).create_attribute_model(initial_axes_to_move)
        self.field_registry.add_attribute_model(
            "axesToMove", self.axes_to_move, self.set_axes_to_move)
        self.set_writeable_in(self.axes_to_move, ss.READY)
        # Create the method models
        self.field_registry.add_method_model(self.validate)
        configure_model = self.field_registry.add_method_model(self.configure)
        self.set_writeable_in(configure_model, ss.READY)
        configure_model.defaults["axesToMove"] = axes_to_move
        self.set_writeable_in(
            self.field_registry.add_method_model(self.run), ss.ARMED)
        self.set_writeable_in(
            self.field_registry.add_method_model(self.abort),
            ss.READY, ss.CONFIGURING, ss.ARMED, ss.RUNNING, ss.POSTRUN,
            ss.PAUSED, ss.SEEKING)
        self.set_writeable_in(
            self.field_registry.add_method_model(self.pause),
            ss.ARMED, ss.PAUSED, ss.RUNNING)
        self.set_writeable_in(
            self.field_registry.add_method_model(self.resume), ss.PAUSED)
        # Override reset to work from aborted too
        self.set_writeable_in(
            self.field_registry.get_field("reset"),
            ss.FAULT, ss.DISABLED, ss.ABORTED, ss.ARMED)
        # Allow Parts to report their status
        self.info_registry.add_reportable(
            RunProgressInfo, self.update_completed_steps)
        # Allow Parts to request extra items from configure
        self.info_registry.add_reportable(
            ConfigureParamsInfo, self.update_configure_params)

    def do_reset(self):
        super(RunnableController, self).do_reset()
        self.configured_steps.set_value(0)
        self.completed_steps.set_value(0)
        self.total_steps.set_value(0)

    def update_configure_params(self, part=None, info=None):
        # type: (Part, ConfigureParamsInfo) -> None
        """Tell controller part needs different things passed to Configure"""
        with self.changes_squashed:
            # Update the dict
            if part:
                self.part_configure_params[part] = info

            # Create a new ConfigureParams subclass from the union of all the
            # call_types
            class ConfigureParamsSubclass(ConfigureParams):
                # This will be serialized, so maintain camelCase for axesToMove
                # noinspection PyPep8Naming
                def __init__(self, generator,
                             axesToMove=self.axes_to_move.value, **kwargs):
                    # type: (AGenerator, UAxesToMove) -> None
                    super(ConfigureParamsSubclass, self).__init__(
                        generator, axesToMove)
                    self.__dict__.update(kwargs)

            # Store it and update its call_types
            configure_model = MethodModel.from_callable(ConfigureParams)
            required = list(configure_model.takes.required)
            self.configure_params_cls = ConfigureParamsSubclass
            ignored = tuple(ConfigureHook.call_types)
            for part in self.parts.values():
                try:
                    info = self.part_configure_params[part]
                except KeyError:
                    continue
                for k, meta in info.metas.items():
                    if k not in ignored:
                        # We don't use this apart from its presence,
                        # so no need to fill in description, typ, etc.
                        ConfigureParamsSubclass.call_types[k] = Anno("")
                        configure_model.takes.elements[k] = meta
                for k in info.required:
                    if k not in required and k not in ignored:
                        required.append(k)
                for k, value in info.defaults.items():
                    if k not in ignored:
                        configure_model.defaults[k] = value
            configure_model.takes.set_required(required)

            # Update methods from the new metas
            self._block.configure.set_takes(configure_model.takes)
            self._block.configure.set_defaults(configure_model.defaults)
            self._block.validate.set_takes(configure_model.takes)
            self._block.validate.set_defaults(configure_model.defaults)
            self._block.validate.set_returns(configure_model.takes)

    def set_axes_to_move(self, value):
        with self.changes_squashed:
            self.axes_to_move.set_value(value)
            self.update_configure_params()

    def _part_params(self, part_contexts=None, params=None):
        # type: (Dict[Part, Context]) -> PartContextParams
        if part_contexts is None:
            part_contexts = self.part_contexts
        if params is None:
            params = self.configure_params
        for part, context in part_contexts.items():
            args = {}
            param_cls = self.part_configure_params.get(part, ConfigureParams)
            for k in param_cls.call_types:
                args[k] = getattr(params, k)
            yield part, context, args

    def validate(self, generator, axes_to_move, **kwargs):
        # type: (AGenerator, AAxesToMove, **Any) -> AConfigureParams
        """Validate configuration parameters and return validated parameters.

        Doesn't take device state into account so can be run in any state
        """
        iterations = 10
        # The validated parameters we will eventually return
        params = self.configure_params_cls(generator, axes_to_move, **kwargs)
        # Make some tasks just for validate
        part_contexts = self.create_part_contexts()
        # Get any status from all parts
        status_part_info = self.run_hooks(
            ReportStatusHook(p, c) for p, c in part_contexts.items())
        while iterations > 0:
            # Try up to 10 times to get a valid set of parameters
            iterations -= 1
            # Validate the params with all the parts
            validate_part_info = self.run_hooks(
                ValidateHook(p, c, status_part_info, **kwargs)
                for p, c, kwargs in self._part_params(part_contexts, params))
            tweaks = ParameterTweakInfo.filter_values(validate_part_info)
            if tweaks:
                for tweak in tweaks:
                    setattr(params, tweak.parameter, tweak.value)
                    self.log.debug(
                        "Tweaking %s to %s", tweak.parameter, tweak.value)
            else:
                # Consistent set, just return the params
                return params
        raise ValueError("Could not get a consistent set of parameters")

    def abortable_transition(self, state):
        with self._lock:
            # We might have been aborted just now, so this will fail
            # with an AbortedError if we were
            self.part_contexts[self].sleep(0)
            self.transition(state)

    @add_call_types
    def configure(self, generator, axes_to_move=AAxesToMove(), **kwargs):
        # type: (AGenerator, AAxesToMove, **Any) -> None
        """Validate the params then configure the device ready for run().

        Try to prepare the device as much as possible so that run() is quick to
        start, this may involve potentially long running activities like moving
        motors.

        Normally it will return in Armed state. If the user aborts then it will
        return in Aborted state. If something goes wrong it will return in Fault
        state. If the user disables then it will return in Disabled state.
        """
        params = self.validate(generator, axes_to_move, **kwargs)
        try:
            self.transition(ss.CONFIGURING)
            self.do_configure(params)
            self.abortable_transition(ss.ARMED)
        except AbortedError:
            self.abort_queue.put(None)
            raise
        except Exception as e:
            self.go_to_error_state(e)
            raise

    def do_configure(self, params):
        # type: (ConfigureParams) -> None
        # These are the part tasks that abort() and pause() will operate on
        self.part_contexts = self.create_part_contexts()
        # So add one for ourself too so we can be aborted
        self.part_contexts[self] = Context(self.process)
        # Store the params for use in seek()
        self.configure_params = params
        # This will calculate what we need from the generator, possibly a long
        # call
        params.generator.prepare()
        # Set the steps attributes that we will do across many run() calls
        self.total_steps.set_value(params.generator.size)
        self.completed_steps.set_value(0)
        self.configured_steps.set_value(0)
        # TODO: We can be cleverer about this and support a different number
        # of steps per run for each run by examining the generator structure
        self.steps_per_run = self._get_steps_per_run(
            params.generator, params.axesToMove)
        # Get any status from all parts
        part_info = self.run_hooks(ReportStatusHook(p, c)
                                   for p, c in self.part_contexts.items())
        # Run the configure command on all parts, passing them info from
        # ReportStatus. Parts should return any reporting info for PostConfigure
        completed_steps = 0
        steps_to_do = self.steps_per_run
        part_info = self.run_hooks(
            ConfigureHook(p, c, completed_steps, steps_to_do, part_info, **kw)
            for p, c, kw in self._part_params())
        # Take configuration info and reflect it as attribute updates
        self.run_hooks(PostConfigureHook(p, c, part_info)
                       for p, c in self.part_contexts.items())
        # Update the completed and configured steps
        self.configured_steps.set_value(steps_to_do)
        # Reset the progress of all child parts
        self.progress_updates = {}
        self.resume_queue = Queue()

    def _get_steps_per_run(self, generator, axes_to_move):
        # type: (CompoundGenerator, List[str]) -> int
        steps = 1
        axes_set = set(axes_to_move)
        for dim in reversed(generator.dimensions):
            # If the axes_set is empty then we are done
            if not axes_set:
                break
            # Consume the axes that this generator scans
            for axis in dim.axes:
                assert axis in axes_set, \
                    "Axis %s is not in %s" % (axis, axes_to_move)
                axes_set.remove(axis)
            # Now multiply by the dimensions to get the number of steps
            steps *= dim.size
        return steps

    @add_call_types
    def run(self):
        # type: () -> None
        """Run a device where configure() has already be called

        Normally it will return in Ready state. If setup for multiple-runs with
        a single configure() then it will return in Armed state. If the user
        aborts then it will return in Aborted state. If something goes wrong it
        will return in Fault state. If the user disables then it will return in
        Disabled state.
        """
        if self.configured_steps.value < self.total_steps.value:
            next_state = ss.ARMED
        else:
            next_state = ss.READY
        try:
            self.transition(ss.RUNNING)
            hook = RunHook
            going = True
            while going:
                try:
                    self.do_run(hook)
                except AbortedError:
                    self.abort_queue.put(None)
                    # Wait for a response on the resume_queue
                    should_resume = self.resume_queue.get()
                    if should_resume:
                        # we need to resume
                        hook = ResumeHook
                        self.log.debug("Resuming run")
                    else:
                        # we don't need to resume, just drop out
                        raise
                else:
                    going = False
            self.abortable_transition(next_state)
        except AbortedError:
            raise
        except Exception as e:
            self.go_to_error_state(e)
            raise

    def do_run(self, hook):
        # type: (Type[ControllerHook]) -> None
        self.run_hooks(hook(p, c) for p, c in self.part_contexts.items())
        self.abortable_transition(ss.POSTRUN)
        completed_steps = self.configured_steps.value
        if completed_steps < self.total_steps.value:
            steps_to_do = self.steps_per_run
            part_info = self.run_hooks(
                ReportStatusHook(p, c) for p, c in self.part_contexts.items())
            self.completed_steps.set_value(completed_steps)
            self.run_hooks(
                PostRunArmedHook(
                    p, c, completed_steps, steps_to_do, part_info, **kwargs)
                for p, c, kwargs in self._part_params())
            self.configured_steps.set_value(completed_steps + steps_to_do)
        else:
            self.run_hooks(
                PostRunReadyHook(p, c) for p, c in self.part_contexts.items())

    def update_completed_steps(self, part, completed_steps):
        # type: (object, RunProgressInfo) -> None
        with self._lock:
            # Update
            self.progress_updates[part] = completed_steps.steps
            min_completed_steps = min(self.progress_updates.values())
            if min_completed_steps > self.completed_steps.value:
                self.completed_steps.set_value(min_completed_steps)

    @add_call_types
    def abort(self):
        # type: () -> None
        """Abort the current operation and block until aborted

        Normally it will return in Aborted state. If something goes wrong it
        will return in Fault state. If the user disables then it will return in
        Disabled state.
        """
        # Tell _call_do_run not to resume
        if self.resume_queue:
            self.resume_queue.put(False)
        self.try_aborting_function(ss.ABORTING, ss.ABORTED, self.do_abort)

    def do_abort(self):
        # type: () -> None
        self.run_hooks(
            AbortHook(p, c) for p, c in self.create_part_contexts().items())

    def try_aborting_function(self, start_state, end_state, func, *args):
        # type: (str, str, Callable[..., None], *Any) -> None
        try:
            # To make the running function fail we need to stop any running
            # contexts (if running a hook) or make transition() fail with
            # AbortedError. Both of these are accomplished here
            with self._lock:
                original_state = self.state.value
                self.abort_queue = Queue()
                self.transition(start_state)
                for context in self.part_contexts.values():
                    context.stop()
            if original_state not in (ss.READY, ss.ARMED, ss.PAUSED):
                # Something was running, let it finish aborting
                try:
                    self.abort_queue.get(timeout=ABORT_TIMEOUT)
                except TimeoutError:
                    self.log.warning("Timeout waiting while %s" % start_state)
            with self._lock:
                # Now we've waited for a while we can remove the error state
                # for transition in case a hook triggered it rather than a
                # transition
                self.part_contexts[self].ignore_stops_before_now()
            func(*args)
            self.abortable_transition(end_state)
        except AbortedError:
            self.abort_queue.put(None)
            raise
        except Exception as e:  # pylint:disable=broad-except
            self.go_to_error_state(e)
            raise

    # Allow camelCase as this will be serialized
    # noinspection PyPep8Naming
    @add_call_types
    def pause(self, completedSteps=0):
        # type: (ACompletedSteps) -> None
        """Pause a run() so that resume() can be called later, or seek within
        an Armed or Paused state.

        The original call to run() will not be interrupted by pause(), it will
        with until the scan completes or is aborted.

        Normally it will return in Paused state. If the user aborts then it will
        return in Aborted state. If something goes wrong it will return in Fault
        state. If the user disables then it will return in Disabled state.
        """
        current_state = self.state.value
        if completedSteps <= 0:
            completed_steps = self.completed_steps.value
        else:
            completed_steps = completedSteps
        if current_state == ss.RUNNING:
            next_state = ss.PAUSED
        else:
            next_state = current_state
        assert completed_steps < self.total_steps.value, \
            "Cannot seek to after the end of the scan"
        self.try_aborting_function(
            ss.SEEKING, next_state, self.do_pause, completed_steps)

    def do_pause(self, completed_steps):
        # type: (int) -> None
        self.run_hooks(
            PauseHook(p, c) for p, c in self.create_part_contexts().items())
        in_run_steps = completed_steps % self.steps_per_run
        steps_to_do = self.steps_per_run - in_run_steps
        part_info = self.run_hooks(
            ReportStatusHook(p, c) for p, c in self.part_contexts.items())
        self.completed_steps.set_value(completed_steps)
        self.run_hooks(
            SeekHook(p, c, completed_steps, steps_to_do, part_info, **kwargs)
            for p, c, kwargs in self._part_params())
        self.configured_steps.set_value(completed_steps + steps_to_do)

    @add_call_types
    def resume(self):
        # type: () -> None
        """Resume a paused scan.

        Normally it will return in Running state. If something goes wrong it
        will return in Fault state.
        """
        self.transition(ss.RUNNING)
        self.resume_queue.put(True)
        # self.run will now take over

    def do_disable(self):
        # type: () -> None
        # Abort anything that is currently running, but don't wait
        for context in self.part_contexts.values():
            context.stop()
        if self.resume_queue:
            self.resume_queue.put(False)
        super(RunnableController, self).do_disable()
