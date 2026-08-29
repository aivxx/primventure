from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from pxr import Sdf, Usd, UsdGeom

from .models import PlayerState, Quest, RunRequest, RunResponse, ValidationResult
from .store import ROOT, WORLD_DIR, SaveStore, level_for_xp, opinion_points_for


TAUNTS = [
    "The System has inspected your opinions. Several have filed for witness protection.",
    "A bold layer. Incorrect, but bold. The crowd has been told this was intentional.",
    "Your authored intent and the composed result are no longer on speaking terms.",
    "SYSTEM: Hydra did not crash. You did. There is a difference.",
    "SYSTEM: Deleting the draft would have been faster. Also, a certification fail.",
]
VICTORIES = [
    "VALIDATION GREEN. The Composition reluctantly returns one city block.",
    "Critical composition hit. Somewhere, a weaker opinion quietly expires.",
    "Room cleared. The System always believed in you, retroactively.",
    "SYSTEM: Competent. Unsettling. Proceed.",
]


class QuestRunner:
    def __init__(self, saves: SaveStore):
        self.saves = saves

    def run(self, quest: Quest, request: RunRequest) -> RunResponse:
        state = self.saves.load()
        locked = [
            requirement
            for requirement in quest.prerequisites
            if requirement not in state.completed_quests
        ]
        if locked or state.level < quest.level_required:
            reason = (
                f"Clear {', '.join(locked)} first."
                if locked
                else f"Crawler level {quest.level_required} required."
            )
            return self._response(quest, state, False, [], "", f"STAIRWELL LOCKED. {reason}")

        question_results = self._validate_questions(quest, request.answers)
        if quest.language == "none":
            results = question_results or [
                ValidationResult(rule="orientation", passed=True, message="Brief acknowledged.")
            ]
            output = ""
            artifact = None
        else:
            artifact, output, execution_error = self._execute(quest, request)
            if execution_error:
                results = question_results + [
                    ValidationResult(rule="execution", passed=False, message=execution_error)
                ]
            else:
                results = question_results + self._validate_stage(
                    artifact, quest.validator.get("assertions", [])
                )

        success = bool(results) and all(result.passed for result in results)
        if success:
            if artifact is not None:
                self._publish(quest, artifact)
            state = self._award(quest, state)
            message = VICTORIES[sum(map(ord, quest.id)) % len(VICTORIES)]
        else:
            message = TAUNTS[sum(map(ord, quest.id)) % len(TAUNTS)]
            if quest.kind.endswith("boss") and state.xp:
                state.xp = max(0, state.xp - min(25, state.xp))
                state.level = level_for_xp(state.xp)
                self.saves.save(state)
                message += " Boss fee: 25 XP."
        return self._response(quest, state, success, results, output, message)

    def _execute(self, quest: Quest, request: RunRequest) -> tuple[Path | None, str, str | None]:
        temp_dir = Path(tempfile.mkdtemp(prefix="primventure-"))
        extension = ".usda" if (request.language or quest.language) == "usda" else ".usd"
        stage_path = temp_dir / f"submission{extension}"
        code = request.code
        if not code.strip():
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None, "", "No authored opinions detected. Submit code or USDA."

        if extension == ".usda":
            stage_path.write_text(code)
            try:
                layer = Sdf.Layer.FindOrOpen(str(stage_path))
                if layer is None:
                    raise ValueError("USD could not open the submitted layer.")
            except Exception as exc:
                return stage_path, "", f"USDA parse failed: {exc}"
            return stage_path, "", None

        if "CreateNew(STAGE_PATH)" not in code:
            self._seed_stage(stage_path)
        script_path = temp_dir / "submission.py"
        prelude = (
            "from pathlib import Path\n"
            f"STAGE_PATH = {str(stage_path)!r}\n"
            "WORLD_ROOT = " + repr(str(WORLD_DIR)) + "\n"
            "ASSET_LIBRARY = "
            + repr(
                str(
                    ROOT
                    / "docs"
                    / "exercise_content"
                    / "composition_arcs"
                    / "lib"
                    / "assets"
                )
            )
            + "\n"
            "EXCHANGE_OBJ = "
            + repr(str(ROOT / "docs" / "exercise_content" / "data_exchange" / "shapes.obj"))
            + "\n"
        )
        script_path.write_text(prelude + "\n" + code + "\n")
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"}
        try:
            completed = subprocess.run(
                [sys.executable, "-I", str(script_path)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except subprocess.TimeoutExpired:
            return stage_path, "", "Execution exceeded the eight-second arena limit."
        output = (completed.stdout + completed.stderr).strip()
        if completed.returncode:
            return stage_path, output, f"Python exited with status {completed.returncode}."
        if not stage_path.exists():
            return stage_path, output, "Code ran, but no stage was saved to STAGE_PATH."
        return stage_path, output, None

    @staticmethod
    def _seed_stage(stage_path: Path) -> None:
        root = WORLD_DIR / "root.usda"
        existing = Usd.Stage.Open(str(root)) if root.exists() else None
        if existing:
            existing.Flatten().Export(str(stage_path))
        else:
            stage = Usd.Stage.CreateNew(str(stage_path))
            stage.DefinePrim("/City", "Xform")
            stage.GetRootLayer().Save()

    def _validate_questions(
        self, quest: Quest, answers: list[int | str]
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for index, question in enumerate(quest.questions):
            supplied = answers[index] if index < len(answers) else ""
            if question.answer is not None:
                passed = supplied == question.answer
            else:
                expected_words = {
                    word.lower().strip(".,")
                    for word in question.answer_key.split()
                    if len(word.strip(".,")) > 5
                }
                supplied_words = {
                    word.lower().strip(".,") for word in str(supplied).split()
                }
                passed = bool(supplied) and len(expected_words & supplied_words) >= min(
                    2, len(expected_words)
                )
            results.append(
                ValidationResult(
                    rule=f"question_{index + 1}",
                    passed=passed,
                    message=(
                        question.explanation or question.answer_key
                        if passed
                        else "Incorrect. Recheck the linked Cookbook page."
                    ),
                )
            )
        return results

    def _validate_stage(
        self, path: Path | None, rules: list[dict[str, Any]]
    ) -> list[ValidationResult]:
        try:
            stage = Usd.Stage.Open(str(path)) if path else None
        except Exception as exc:
            return [ValidationResult(rule="stage_open", passed=False, message=str(exc))]
        if stage is None:
            return [
                ValidationResult(
                    rule="stage_open", passed=False, message="The submitted stage could not be opened."
                )
            ]
        results: list[ValidationResult] = []
        for rule in rules:
            name = str(rule.get("rule") or rule.get("type") or next(iter(rule), "unknown"))
            try:
                passed, message = self._check(stage, name, rule)
            except Exception as exc:
                passed, message = False, f"Validator error: {exc}"
            results.append(ValidationResult(rule=name, passed=passed, message=message))
        if not rules:
            results.append(
                ValidationResult(rule="stage_open", passed=True, message="Stage opens successfully.")
            )
        return results

    @staticmethod
    def _check(stage: Usd.Stage, name: str, rule: dict[str, Any]) -> tuple[bool, str]:
        payload = rule.get(name)
        if isinstance(payload, dict):
            data = payload
        elif payload is not None:
            data = {"path": payload} if name == "prim_exists" else {"value": payload}
        else:
            data = rule
        path = data.get("path")
        expected = data.get("value", data.get("expected"))
        prim = stage.GetPrimAtPath(path) if path else None
        if name == "prim_exists":
            passed = bool(prim and prim.IsValid())
        elif name == "prim_type":
            passed = bool(prim and prim.GetTypeName() == expected)
        elif name == "attribute_equals":
            attribute = (
                stage.GetAttributeAtPath(path)
                if path and "." in path
                else prim.GetAttribute(data["attribute"]) if prim else None
            )
            value = attribute.Get(data["time"]) if attribute and "time" in data else attribute.Get() if attribute else None
            value = QuestRunner._as_plain(value)
            expected_plain = QuestRunner._as_plain(expected)
            passed = value == expected_plain
        elif name == "metadata_equals":
            target = prim if prim else stage
            value = target.GetMetadata(data.get("metadata", data.get("key"))) if target else None
            field = data.get("field")
            if field and isinstance(value, dict):
                value = value.get(field)
            passed = value == expected
        elif name == "kind_equals":
            passed = bool(prim and prim.IsValid() and Usd.ModelAPI(prim).GetKind() == expected)
        elif name == "has_reference":
            passed = bool(prim and prim.HasAuthoredReferences())
            if passed and data.get("asset"):
                references = prim.GetMetadata("references")
                passed = any(
                    Path(item.assetPath).name == Path(str(data["asset"])).name
                    for item in references.GetAppliedItems()
                )
        elif name == "has_payload":
            passed = bool(prim and prim.HasAuthoredPayloads())
            if passed and data.get("asset"):
                payloads = prim.GetMetadata("payload")
                passed = any(
                    Path(item.assetPath).name == Path(str(data["asset"])).name
                    for item in payloads.GetAppliedItems()
                )
        elif name == "has_inherit":
            passed = bool(prim and prim.HasAuthoredInherits())
        elif name == "has_specializes":
            passed = bool(prim and prim.HasAuthoredSpecializes())
        elif name == "has_variant_set":
            variant_name = data.get("variant_set", data.get("name"))
            variant_set = prim.GetVariantSet(variant_name) if prim else None
            required = set(data.get("variants", []))
            passed = bool(
                variant_set
                and (not required or required.issubset(set(variant_set.GetVariantNames())))
                and (
                    not data.get("selection")
                    or variant_set.GetVariantSelection() == data["selection"]
                )
            )
        elif name == "active":
            passed = bool(prim and prim.IsValid() and prim.IsActive() == bool(expected if expected is not None else True))
        elif name == "instanceable":
            passed = bool(prim and prim.IsValid() and prim.IsInstanceable() == bool(expected if expected is not None else True))
        elif name == "specifier_equals":
            specifiers = {
                "def": Sdf.SpecifierDef,
                "over": Sdf.SpecifierOver,
                "class": Sdf.SpecifierClass,
            }
            passed = bool(prim and prim.GetSpecifier() == specifiers.get(str(expected).lower()))
        elif name == "prim_stack":
            stack = list(prim.GetPrimStack()) if prim else []
            required = [str(item).lower() for item in data.get("specifiers", [])]
            actual = [
                {
                    Sdf.SpecifierDef: "def",
                    Sdf.SpecifierOver: "over",
                    Sdf.SpecifierClass: "class",
                }.get(spec.specifier, "unknown")
                for spec in stack
            ]
            passed = len(stack) >= int(data.get("min", 1)) and all(
                item in actual for item in required
            )
        elif name == "sublayer_order":
            actual = [Path(item).name for item in stage.GetRootLayer().subLayerPaths]
            wanted = [Path(item).name for item in data.get("layers", [])]
            passed = actual == wanted if data.get("exact") or wanted == [] else actual[: len(wanted)] == wanted
        elif name == "layer_offset":
            references = prim.GetMetadata("references") if prim else None
            items = list(references.GetAppliedItems()) if references else []
            offsets = [item.layerOffset.offset for item in items]
            scales = [item.layerOffset.scale for item in items]
            passed = bool(items) and (
                data.get("offset") is None or data["offset"] in offsets
            ) and (data.get("scale") is None or data["scale"] in scales)
        elif name == "attribute_source":
            attribute = stage.GetAttributeAtPath(path) if path else None
            stack = attribute.GetPropertyStack() if attribute else []
            source = Path(stack[0].layer.identifier).name if stack else ""
            passed = bool(stack and source == Path(str(data.get("layer"))).name)
        elif name == "traversal_contains":
            traversed = {str(item.GetPath()) for item in stage.Traverse()}
            passed = all(item in traversed for item in data.get("paths", [])) and all(
                item not in traversed for item in data.get("excluded", [])
            )
        elif name == "default_prim":
            default = stage.GetDefaultPrim()
            passed = bool(default and (not expected or default.GetPath().pathString == expected))
        elif name == "up_axis":
            passed = UsdGeom.GetStageUpAxis(stage) == expected
        elif name == "meters_per_unit":
            passed = UsdGeom.GetStageMetersPerUnit(stage) == float(expected)
        elif name == "point_instancer":
            instancer = UsdGeom.PointInstancer(prim) if prim else None
            indices = instancer.GetProtoIndicesAttr().Get() if instancer else None
            positions = instancer.GetPositionsAttr().Get() if instancer else None
            targets = list(instancer.GetPrototypesRel().GetTargets()) if instancer else []
            passed = bool(
                instancer
                and instancer.GetPrim().IsValid()
                and indices
                and positions
                and len(indices) == len(positions)
                and len(indices) >= int(data.get("min_instances", 1))
                and (
                    data.get("prototype_count") is None
                    or len(targets) == int(data["prototype_count"])
                )
            )
        elif name == "start_time":
            passed = stage.GetStartTimeCode() == expected
        elif name == "end_time":
            passed = stage.GetEndTimeCode() == expected
        else:
            return False, f"Unknown validation rule {name!r}."
        detail = data.get("message") or f"{name}: expected {expected!r}"
        return passed, detail

    @staticmethod
    def _as_plain(value: Any) -> Any:
        if value is None or isinstance(value, (str, bytes, bool, int, float)):
            return value
        if isinstance(value, dict):
            return {key: QuestRunner._as_plain(item) for key, item in value.items()}
        if hasattr(value, "__len__") and not isinstance(value, (str, bytes)):
            try:
                return [QuestRunner._as_plain(item) for item in list(value)]
            except TypeError:
                pass
        return value

    def _publish(self, quest: Quest, artifact: Path) -> None:
        if quest.world_target and not quest.world_target.startswith("/"):
            destination = (WORLD_DIR / quest.world_target).resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(artifact, destination)
        else:
            bundle = (WORLD_DIR / "workstreams" / quest.id).resolve()
            bundle.mkdir(parents=True, exist_ok=True)
            destination = bundle / f"submission{artifact.suffix}"
            shutil.copy2(artifact, destination)
            for support in artifact.parent.iterdir():
                if support == artifact or support.suffix.lower() not in {
                    ".usd",
                    ".usda",
                    ".usdc",
                    ".obj",
                    ".mtl",
                }:
                    continue
                shutil.copy2(support, bundle / support.name)
        if WORLD_DIR.resolve() not in destination.parents:
            raise ValueError("world_target must stay inside world/")
        root_path = WORLD_DIR / "root.usda"
        root = Sdf.Layer.FindOrOpen(str(root_path)) or Sdf.Layer.CreateNew(str(root_path))
        relative_asset = os.path.relpath(destination, root_path.parent).replace(os.sep, "/")
        legacy_asset = f"workstreams/{quest.id}.usd"
        if legacy_asset in root.subLayerPaths:
            root.subLayerPaths.remove(legacy_asset)
        if relative_asset not in root.subLayerPaths:
            root.subLayerPaths.append(relative_asset)
            root.Save()

    def _award(self, quest: Quest, state: PlayerState) -> PlayerState:
        first_clear = quest.id not in state.completed_quests
        if first_clear:
            state.completed_quests.append(quest.id)
            state.xp += quest.xp
            state.level = level_for_xp(state.xp)
            stat_domains = {
                "craft": "Authoring",
                "resolve": "Composition",
                "insight": "Debug",
                "lore": "Pipeline",
            }
            for stat, amount in quest.stats.items():
                domain = stat_domains.get(stat, stat)
                state.stats[domain] = state.stats.get(domain, 0) + amount
            for recipe in quest.recipes:
                if recipe not in state.recipes:
                    state.recipes.append(recipe)
            reward = quest.reward if isinstance(quest.reward, dict) else {}
            if isinstance(quest.reward, str) and quest.reward:
                state.inventory[quest.reward] = state.inventory.get(quest.reward, 0) + 1
            state.opinion_points += opinion_points_for(quest)
            achievement = reward.get("achievement")
            if achievement and achievement not in state.achievements:
                state.achievements.append(achievement)
            for item, count in reward.get("inventory", {}).items():
                state.inventory[item] = state.inventory.get(item, 0) + int(count)
        return self.saves.save(state)

    @staticmethod
    def _response(
        quest: Quest,
        state: PlayerState,
        success: bool,
        results: list[ValidationResult],
        output: str,
        message: str,
    ) -> RunResponse:
        return RunResponse(
            success=success,
            quest_id=quest.id,
            results=results,
            output=output,
            system_message=message,
            state=state.model_dump(),
        )

