"""Regression tests for previously confirmed bugs.

Each test documents a behavior that was once broken; keep them passing.
"""
import copy
import pickle
import sys
from functools import partial
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import pytest

from ..config import ConfigBase
from ..from_commandline import make_config, make_config_from_cli
from ..from_dict import make_config_from_flat_dict
from ..from_file import load_config_from_file


class OptimizerConfig(ConfigBase):
    pass

class Adam(OptimizerConfig):
    lr: float = 1e-3
    weight_decay: float = 0.01

class SGD(OptimizerConfig):
    lr: float = 1e-2
    momentum: float = 0.9


def test_pep604_union_fields():
    """SubConfig | None must behave exactly like Optional[SubConfig]."""
    class Train(ConfigBase):
        opt: OptimizerConfig | None = None
        sched: Optional[OptimizerConfig] = None

    cfg = make_config_from_flat_dict(Train, {"opt": "adam", "opt.lr": "0.1", "sched": "sgd"})
    assert isinstance(cfg.opt, Adam)
    assert cfg.opt.lr == 0.1
    assert isinstance(cfg.sched, SGD)


def test_mutable_defaults_not_shared():
    """Mutating one instance's default must not affect other instances."""
    class Model(ConfigBase):
        layers: list = [1, 2]
        opt: OptimizerConfig = Adam()

    first, second = Model(), Model()
    first.layers.append(99)
    first.opt.lr = 42
    assert second.layers == [1, 2]
    assert second.opt.lr == 1e-3


def test_callable_defaults():
    """Fields with function/partial defaults keep their declared default."""
    def relu(x):
        return x

    class Model(ConfigBase):
        activation: Callable = relu
        factory: Callable = partial(int, 5)

    model = Model()
    assert model.activation is relu
    assert model.factory() == 5


def test_inherited_required_fields_checked():
    """Required fields declared on a parent class are still required in children."""
    class Base(ConfigBase):
        lr: float

    class Child(Base):
        name: str = "child"

    with pytest.raises(ValueError):
        Child()
    assert Child(lr=0.1).lr == 0.1


def test_unknown_kwargs_rejected():
    """Typos in constructor kwargs raise instead of silently creating attributes."""
    class Model(ConfigBase):
        layers: int = 4

    with pytest.raises(ValueError):
        Model(layerz=8)


def test_recursive_instantiate_containers():
    """Configs nested in dicts and tuples are instantiated too."""
    class Item(ConfigBase):
        _target_class = dict
        name: str = "x"

    class Holder(ConfigBase):
        _target_class = dict
        items: Dict[str, Item] = {}
        pair: Tuple[Item, Item] = (Item(), Item(name="y"))

    result = Holder(items={"a": Item(name="a")}).instantiate()
    assert result["items"]["a"] == {"name": "a"}
    assert result["pair"][1] == {"name": "y"}


def test_to_dict_converts_configs_in_containers():
    """to_dict must not leak live ConfigBase objects inside lists/dicts."""
    class Holder(ConfigBase):
        opts: Dict[str, OptimizerConfig] = {}
        schedule: list = []

    holder = Holder(opts={"a": Adam()}, schedule=[SGD()])
    dumped = holder.to_dict()
    assert isinstance(dumped["opts"]["a"], dict)
    assert dumped["opts"]["a"]["_config_name"] == "adam"
    assert isinstance(dumped["schedule"][0], dict)


def test_round_trip_preserves_subclass():
    """to_dict -> rebuild returns the same subclasses and values."""
    class Train(ConfigBase):
        opt: OptimizerConfig = Adam()
        epochs: int = 10

    original = Train(opt=SGD(momentum=0.5), epochs=3)
    rebuilt = make_config_from_flat_dict(Train, original.to_dict(flatten=True))
    assert isinstance(rebuilt.opt, SGD)
    assert rebuilt.opt.momentum == 0.5
    assert rebuilt == original


def test_make_config_typed_overrides():
    """make_config(instance) must accept non-string override values unchanged."""
    class Train(ConfigBase):
        mapping: Dict[str, int] = {}
        opt: OptimizerConfig = Adam()

    base = Train(mapping={"a": 1})
    updated = make_config(base, **{"mapping": {"b": 2}, "opt.lr": 0.5})
    assert updated.mapping == {"b": 2}
    assert isinstance(updated.opt, Adam)
    assert updated.opt.lr == 0.5
    # and the original is untouched
    assert base.mapping == {"a": 1}


def test_none_strings_are_not_converted():
    """A legitimate 'none' string value must survive to_dict round trips."""
    class Model(ConfigBase):
        norm: str = "none"

    assert Model().to_dict()["norm"] == "none"
    assert make_config(Model(), norm="None").norm == "None"


def test_bunch_behaves_like_an_object():
    """Attribute protocol on to_dict() results: hasattr/getattr/deepcopy."""
    dumped = Adam().to_dict()
    assert not hasattr(dumped, "missing")
    assert getattr(dumped, "missing", "fallback") == "fallback"
    assert copy.deepcopy(dumped) == dumped
    with pytest.raises(AttributeError):
        dumped.missing


def test_file_loaded_configs_pickle(tmp_path):
    """Configs loaded from a file must be picklable (e.g. inside checkpoints)."""
    src_root = Path(__file__).resolve().parents[2]
    (tmp_path / "conf.py").write_text(
        f"import sys\nsys.path.insert(0, {str(src_root)!r})\n"
        "from zencfg import ConfigBase\n"
        "class FileModel(ConfigBase):\n"
        "    layers: int = 3\n"
    )
    FileModel = load_config_from_file(tmp_path, "conf.py", "FileModel")
    restored = pickle.loads(pickle.dumps(FileModel(layers=7)))
    assert restored.layers == 7
    # loading again returns the same class: isinstance stays consistent
    assert load_config_from_file(tmp_path, "conf.py", "FileModel") is FileModel


def test_forward_reference_failure_is_loud():
    """A bad annotation must raise at class definition, not silently disable validation."""
    with pytest.raises(Exception):
        class Broken(ConfigBase):
            value: "NoSuchType" = None  # noqa: F821
        Broken()


def test_defaults_are_validated():
    """Class-attribute defaults are coerced and validated at instantiation."""
    class Model(ConfigBase):
        lr: float = "1e-3"

    assert Model().lr == 0.001

    class Broken(ConfigBase):
        n: int = "not_a_number"

    with pytest.raises(TypeError):
        Broken()


def test_nested_errors_are_aggregated():
    """Errors across fields are reported together; key errors win the exception type."""
    class Outer(ConfigBase):
        required_field: int
        opt: OptimizerConfig = Adam()

    with pytest.raises(ValueError) as excinfo:
        Outer(opt={"_config_name": "adam", "lr": "abc"})
    assert "required_field" in str(excinfo.value)
    assert "lr" in str(excinfo.value)


def test_unannotated_class_attributes_stay_inert():
    """Callable instances and classes as plain attributes are not fields."""
    class Scale:
        def __call__(self, x):
            return x * 2

    class Model(ConfigBase):
        transform = Scale()
        helper_cls = dict
        x: int = 1

    model = Model()
    assert model.transform(3) == 6
    assert model.helper_cls is dict
    assert set(Model.model_fields) == {"x"}


def test_any_fields_parse_json_but_untyped_stay_raw():
    from typing import Any

    class Model(ConfigBase):
        anyf: Any = None
        bare = "raw"

    cfg = make_config_from_flat_dict(Model, {"anyf": "[1, 2]", "bare": "8"})
    assert cfg.anyf == [1, 2]
    assert cfg.bare == "8"


def test_sibling_subclass_rejected_for_narrow_annotation():
    """A field annotated with a leaf class must not accept sibling classes."""
    class Model(ConfigBase):
        opt: Adam = Adam()

    with pytest.raises(ValueError):
        make_config_from_flat_dict(Model, {"opt": "sgd"})
    assert make_config_from_flat_dict(Model, {"opt": "adam", "opt.lr": "0.5"}).opt.lr == 0.5


def test_configs_are_hashable():
    first, second = Adam(), Adam()
    assert first == second               # value equality
    assert len({first, second}) == 2     # identity hash, both usable in sets
    assert {first: "x"}[first] == "x"


def test_cli_switches_subclass_on_instance_source(monkeypatch):
    """--field name must select a subclass even when the source is an instance."""
    class Train(ConfigBase):
        opt: OptimizerConfig = Adam(lr=0.5)
        epochs: int = 2

    monkeypatch.setattr("sys.argv", ["prog", "--opt", "sgd", "--opt.momentum", "0.7"])
    cfg = make_config_from_cli(Train())
    assert isinstance(cfg.opt, SGD)
    assert cfg.opt.momentum == 0.7

    monkeypatch.setattr("sys.argv", ["prog", "--opt.lr", "0.9"])
    cfg = make_config_from_cli(Train())
    assert isinstance(cfg.opt, Adam)
    assert cfg.opt.lr == 0.9
    assert cfg.epochs == 2


def test_dotted_override_into_dict_of_configs_keeps_siblings():
    class Zoo(ConfigBase):
        experts: Dict[str, OptimizerConfig] = {}

    zoo = Zoo(experts={"a": Adam(lr=1.0), "b": SGD()})
    updated = make_config(zoo, **{"experts.a.lr": 2.0})
    assert set(updated.experts) == {"a", "b"}
    assert updated.experts["a"].lr == 2.0


def test_class_level_default_access():
    """Field defaults stay readable on the class, like regular attributes."""
    assert Adam.lr == 1e-3
    assert hasattr(Adam, "weight_decay")
    assert not hasattr(Adam, "no_such_field")


def test_unannotated_default_override_keeps_inherited_type():
    class Base(ConfigBase):
        layers: int = 4

    class Child(Base):
        layers = 8

    assert Child().layers == 8
    assert Child(layers="12").layers == 12
    with pytest.raises(TypeError):
        Child(layers="abc")


def test_reannotated_untyped_field_gets_string_parsing():
    """Re-annotating a field that was un-annotated in a parent enables parsing."""
    from typing import List

    class Parent(ConfigBase):
        x = 5

    class Child(Parent):
        x: List[int] = [1, 2]

    assert Child(x="[4, 5]").x == [4, 5]


def test_shadow_warnings_only_for_genuine_shadows():
    """Overriding a default is silent; shadowing a real method still warns."""
    import warnings

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        class Base(ConfigBase):
            n: int = 1

        class Quiet(Base):
            n = 2

    assert not any("shadows" in str(w.message) for w in caught)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        class WithMethod(ConfigBase):
            def helper(self):
                return 1

        class Loud(WithMethod):
            helper: str = "x"

    assert any("helper" in str(w.message) and "shadows" in str(w.message) for w in caught)


def test_class_access_with_default_factory():
    from pydantic import Field

    class Model(ConfigBase):
        items: list = Field(default_factory=lambda: [1, 2])

    assert Model.items == [1, 2]
    assert Model().items == [1, 2]


def test_fields_set_tracks_only_explicit_values():
    class Model(ConfigBase):
        opt: OptimizerConfig = Adam()
        n: int = 1

    assert Model().model_fields_set == set()
    assert Model(n=5).model_fields_set == {"n"}


def test_dict_of_config_defaults_merge_from_class():
    """Dotted overrides into a Dict[str, Config] field merge with the default."""
    class Zoo(ConfigBase):
        experts: Dict[str, OptimizerConfig] = {"a": Adam(lr=1.0), "b": Adam(lr=2.0)}

    zoo = make_config_from_flat_dict(Zoo, {"experts.a.lr": "3.0"})
    assert zoo.experts["a"].lr == 3.0
    assert zoo.experts["b"].lr == 2.0  # sibling preserved


def test_bare_same_name_reselect_keeps_instance_values(monkeypatch):
    """--opt adam when the instance already holds an Adam keeps its values."""
    class Train(ConfigBase):
        opt: OptimizerConfig = Adam(lr=0.5)

    monkeypatch.setattr("sys.argv", ["prog", "--opt", "adam"])
    assert make_config_from_cli(Train()).opt.lr == 0.5

    monkeypatch.setattr("sys.argv", ["prog", "--opt", "sgd"])
    assert isinstance(make_config_from_cli(Train()).opt, SGD)


def test_non_string_config_name_is_a_clear_error():
    class Train(ConfigBase):
        opt: OptimizerConfig = Adam()

    with pytest.raises(ValueError, match="must be a string"):
        make_config_from_flat_dict(Train, {"opt": {"_config_name": 123}})


def test_pep563_annotations_resolve_in_parent_module(tmp_path, monkeypatch):
    """An un-annotated default override works when the parent's module uses
    `from __future__ import annotations` and the child imports under an alias."""
    import subprocess
    import sys

    src_root = Path(__file__).resolve().parents[2]
    (tmp_path / "parent_mod.py").write_text(
        "from __future__ import annotations\n"
        f"import sys; sys.path.insert(0, {str(src_root)!r})\n"
        "from zencfg import ConfigBase\n"
        "class SubThing(ConfigBase):\n    x: int = 1\n"
        "class Parent(ConfigBase):\n    sub: SubThing = SubThing()\n")
    (tmp_path / "child_mod.py").write_text(
        "from parent_mod import Parent, SubThing as ST\n"
        "class Child(Parent):\n    sub = ST(x=2)\n")
    result = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, {str(tmp_path)!r}); "
         "from child_mod import Child; print(Child().sub.x)"],
        capture_output=True, text=True)
    assert result.stdout.strip() == "2", result.stderr
