"""The assistant is a thin conversational layer. It never plans, ranks or books by itself: every action goes through
the existing recommendation, itinerary and booking services, which validate and authorise it. Destructive edits need
an explicit confirmation turn."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.integrations.llm.base import LLMClient, LLMError, extract_json
from app.integrations.llm.providers import get_llm
from app.models.booking import AssistantConversation, AssistantMessage
from app.models.catalog import Destination
from app.models.itinerary import Itinerary
from app.models.user import User
from app.modules.assistant import nlu
from app.modules.assistant.i18n import STATUS_HI, tr
from app.modules.bookings.service import BookingService
from app.modules.itinerary.service import ItineraryService
from app.modules.recommendations.service import RecommendationService
from app.schemas.assistant import ActionOut, ChatOut, ConversationDetail, ConversationSummary, MessageOut
from app.schemas.itinerary import AddActivity, ReorderRequest, TripRequest
from app.schemas.recommendations import PreferenceOverrides, RecommendationRequest

log = logging.getLogger("routeaura.assistant")
INTENTS = {
    "greeting",
    "help",
    "recommend",
    "plan",
    "show",
    "remove",
    "add",
    "move",
    "booking",
    "hotels",
    "yes",
    "no",
    "unknown",
}


class AssistantService:
    def __init__(self, db: Session, llm: LLMClient | None = None):
        self.db = db
        self.llm = llm if llm is not None else get_llm()

    # ------------------------------------------------------------------ conversations
    def _conversation(self, user: User, cid: uuid.UUID) -> AssistantConversation:
        c = self.db.scalar(
            select(AssistantConversation).where(
                AssistantConversation.id == cid, AssistantConversation.user_id == user.id
            )
        )
        if c is None:
            raise not_found("Conversation")
        return c

    def list(self, user: User, page: int, page_size: int):
        base = select(AssistantConversation).where(AssistantConversation.user_id == user.id)
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self.db.scalars(
            base.order_by(AssistantConversation.updated_at.desc(), AssistantConversation.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [self._summary(c) for c in rows], total

    def _summary(self, c: AssistantConversation) -> ConversationSummary:
        n = (
            self.db.scalar(
                select(func.count()).select_from(AssistantMessage).where(AssistantMessage.conversation_id == c.id)
            )
            or 0
        )
        return ConversationSummary(
            id=c.id, title=c.title, language=c.language, updated_at=c.updated_at, message_count=n
        )

    def detail(self, user: User, cid: uuid.UUID) -> ConversationDetail:
        c = self._conversation(user, cid)
        msgs = [
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                language=m.language,
                input_mode=m.input_mode,
                actions=m.actions,
                cards=m.cards,
                created_at=m.created_at,
            )
            for m in c.messages
        ]
        return ConversationDetail(**self._summary(c).model_dump(), messages=msgs)

    def patch(self, user: User, cid: uuid.UUID, language: str | None, title: str | None) -> ConversationSummary:
        c = self._conversation(user, cid)
        if language:
            c.language = language
        if title:
            c.title = title
        self.db.commit()
        return self._summary(c)

    def delete(self, user: User, cid: uuid.UUID) -> None:
        self.db.delete(self._conversation(user, cid))
        self.db.commit()

    # ------------------------------------------------------------------ understanding
    def _understand(self, text: str, lang: str, names: dict[str, str]) -> nlu.Understanding:
        rules = nlu.understand(text, lang, names)
        if self.llm.name == "none" or rules.intent in ("yes", "no"):
            return rules
        try:
            raw = self.llm.complete(
                'Classify the traveler\'s message. Reply ONLY with JSON: {"intent": one of '
                + ", ".join(sorted(INTENTS - {"yes", "no"}))
                + ', "destination": string|null, "days": integer|null, "travelers": integer|null}. Use unknown when unsure.',
                text,
                max_tokens=200,
            )
            obj = extract_json(raw)
            if not isinstance(obj, dict) or obj.get("intent") not in INTENTS:
                raise ValueError("invalid intent")
            u = nlu.Understanding(obj["intent"], rules.slots, lang, matched_by="llm")
            if isinstance(obj.get("days"), int) and 1 <= obj["days"] <= 14 and u.slots.days is None:
                u.slots.days = obj["days"]
            if isinstance(obj.get("destination"), str) and u.slots.destination is None:
                u.slots.destination = nlu.extract_destination(obj["destination"].lower(), names)
            return u
        except (LLMError, ValueError):
            return rules  # never depend on the model: the rule-based reading stays the fallback

    # ------------------------------------------------------------------ chat
    def chat(
        self, user: User, message: str, conversation_id: uuid.UUID | None, language: str | None, input_mode: str
    ) -> ChatOut:
        detected, _ = nlu.detect_language(message)
        if conversation_id:
            conv = self._conversation(user, conversation_id)
            if language and language != conv.language:
                conv.language = language
        else:
            conv = AssistantConversation(user_id=user.id, language=language or detected, title=message[:60], state={})
            self.db.add(conv)
            self.db.flush()
        lang = conv.language
        dests = {
            d.slug: d.name
            for d in self.db.scalars(
                select(Destination).where(Destination.is_published.is_(True), Destination.deleted_at.is_(None))
            )
        }
        u = self._understand(message, lang, dests)
        state = dict(conv.state or {})
        actions: list[ActionOut] = []
        cards: list[dict] = []
        pending = state.get("pending")
        try:
            reply = self._dispatch(user, u, lang, dests, state, pending, actions, cards)
        except AppError as exc:
            reply = tr("error", lang, msg=exc.message)
            actions.append(ActionOut(type=u.intent, status="failed", detail={"code": exc.code}))
        except Exception:  # noqa: BLE001
            log.exception("assistant dispatch failed")
            reply = tr("error", lang, msg="unexpected error")
            actions.append(ActionOut(type=u.intent, status="failed", detail={"code": "internal_error"}))
        conv.state = state
        self.db.add(
            AssistantMessage(
                conversation_id=conv.id, role="user", content=message, language=detected, input_mode=input_mode
            )
        )
        self.db.add(
            AssistantMessage(
                conversation_id=conv.id,
                role="assistant",
                content=reply,
                language=lang,
                input_mode="text",
                actions=[a.model_dump() for a in actions],
                cards=cards,
            )
        )
        conv.updated_at = func.now()
        self.db.commit()
        return ChatOut(
            conversation_id=conv.id,
            language=lang,
            detected_language=detected,
            language_mismatch=detected != lang and message.strip() != "",
            reply=reply,
            actions=actions,
            cards=cards,
            awaiting_confirmation=bool((state.get("pending") or {}).get("type") == "confirm"),
            interpreted_by=u.matched_by,
        )

    # ------------------------------------------------------------------ dispatch
    def _dispatch(
        self,
        user,
        u: nlu.Understanding,
        lang: str,
        dests: dict[str, str],
        state: dict,
        pending: dict | None,
        actions: list[ActionOut],
        cards: list[dict],
    ) -> str:
        intent, s = u.intent, u.slots
        if s.destination:
            state["destination"] = s.destination

        if pending and pending.get("type") == "confirm":
            if intent == "yes":
                state.pop("pending", None)
                return self._execute_confirmed(user, pending, lang, actions, cards)
            if intent == "no":
                state.pop("pending", None)
                actions.append(ActionOut(type=pending["action"], status="failed", detail={"reason": "declined"}))
                return tr("cancelled", lang)
            state.pop("pending", None)  # any other message abandons the pending change (never executed implicitly)
        elif intent in ("yes", "no"):
            if not (pending and pending.get("type") == "slots"):
                return tr("nothing_pending", lang)

        if pending and pending.get("type") == "slots" and intent in ("unknown", "yes", "no", "plan", "recommend"):
            merged = pending["slots"]
            merged["destination"] = s.destination or merged.get("destination")
            merged["days"] = (
                s.days
                or merged.get("days")
                or (int(s.activity_text) if (s.activity_text or "").strip().isdigit() else None)
            )
            for k, v in (("budget_minor", s.budget_minor), ("travelers", s.travelers)):
                merged[k] = v or merged.get(k)
            merged["interests"] = s.interests or merged.get("interests", [])
            state.pop("pending", None)
            return self._plan(user, merged, lang, dests, state, actions, cards)

        if intent == "greeting":
            return tr("greeting", lang)
        if intent == "help":
            return tr("help", lang)
        if intent == "recommend":
            return self._recommend(user, s, lang, actions, cards)
        if intent == "plan":
            return self._plan(
                user,
                {
                    "destination": s.destination or state.get("destination"),
                    "days": s.days,
                    "budget_minor": s.budget_minor,
                    "travelers": s.travelers,
                    "interests": s.interests,
                },
                lang,
                dests,
                state,
                actions,
                cards,
            )
        if intent == "show":
            return self._show(user, lang, state, actions, cards)
        if intent in ("remove", "move", "add"):
            return self._edit(user, intent, s, lang, state, actions, cards)
        if intent == "booking":
            return self._bookings(user, lang, actions, cards)
        if intent == "hotels":
            return self._hotels(user, s.destination or state.get("destination"), lang, dests, actions, cards)
        return tr("unknown", lang)

    def _recommend(self, user, s: nlu.Slots, lang: str, actions, cards) -> str:
        overrides = {}
        if s.interests:
            overrides["interests"] = s.interests
        if s.budget_minor and s.days:
            overrides["budget_per_day_minor"] = s.budget_minor // max(1, s.days)
        res = RecommendationService(self.db).recommend(
            user, "destination", RecommendationRequest(overrides=PreferenceOverrides(**overrides), page_size=3)
        )
        if not res.items:
            actions.append(ActionOut(type="recommend", status="failed", detail={"reason": "no_results"}))
            return tr("recommend_none", lang)
        lines = [tr("recommend_intro", lang)]
        for it in res.items:
            reason = it.reasons[0] if it.reasons else (it.cautions[0] if it.cautions else "")
            lines.append(f"{it.rank}. {it.destination.name}" + (f": {reason}" if reason else ""))
            cards.append(
                {
                    "type": "destination",
                    "slug": it.destination.slug,
                    "name": it.destination.name,
                    "score": it.score,
                    "reasons": it.reasons[:2],
                }
            )
        if res.strategy == "popularity_fallback":
            lines.append(tr("recommend_fallback", lang))
        actions.append(
            ActionOut(type="recommend", status="ok", detail={"run_id": str(res.run_id), "strategy": res.strategy})
        )
        return "\n".join(lines)

    def _plan(self, user, slots: dict, lang: str, dests: dict[str, str], state: dict, actions, cards) -> str:
        if not slots.get("destination"):
            state["pending"] = {"type": "slots", "intent": "plan", "slots": slots}
            actions.append(ActionOut(type="plan", status="needs_info", detail={"missing": "destination"}))
            return tr("ask_destination", lang, names=", ".join(sorted(dests.values())))
        if not slots.get("days"):
            state["pending"] = {"type": "slots", "intent": "plan", "slots": slots}
            actions.append(ActionOut(type="plan", status="needs_info", detail={"missing": "days"}))
            return tr("ask_days", lang)
        dest = self.db.scalar(
            select(Destination).where(
                Destination.slug == slots["destination"],
                Destination.is_published.is_(True),
                Destination.deleted_at.is_(None),
            )
        )
        if dest is None:
            return tr("ask_destination", lang, names=", ".join(sorted(dests.values())))
        req = TripRequest(
            destination_id=dest.id,
            days=int(slots["days"]),
            travelers=slots.get("travelers") or 1,
            budget_total_minor=slots.get("budget_minor"),
            interests=slots.get("interests") or None,
            title=None,
            use_llm=True,
        )
        it = ItineraryService(self.db, llm=self.llm).generate(user, req)
        state["itinerary_id"], state["destination"] = str(it.id), dest.slug
        n = sum(len(d.activities) for d in it.day_plans)
        summary = self._lines(it, lang)
        out = tr("plan_done", lang, days=it.days, dest=dest.name, n=n, summary="\n" + summary)
        if it.violations:
            out += "\n" + tr("plan_issue", lang, n=len(it.violations))
        if it.generation_source != "llm":
            out += "\n" + tr("plan_fallback", lang)
        cards.append({"type": "itinerary", "id": str(it.id), "title": it.title})
        actions.append(
            ActionOut(type="plan", status="ok", detail={"itinerary_id": str(it.id), "source": it.generation_source})
        )
        return out

    def _current_itinerary(self, user: User, state: dict) -> Itinerary | None:
        if state.get("itinerary_id"):
            try:
                return ItineraryService(self.db, llm=self.llm)._own(user, uuid.UUID(state["itinerary_id"]))
            except AppError:
                state.pop("itinerary_id", None)
        it = self.db.scalar(
            select(Itinerary)
            .where(Itinerary.user_id == user.id, Itinerary.deleted_at.is_(None))
            .order_by(Itinerary.updated_at.desc())
        )
        if it:
            state["itinerary_id"] = str(it.id)
        return it

    @staticmethod
    def _lines(it, lang: str) -> str:
        out = []
        for d in it.day_plans:
            items = ", ".join(f"{a.start_time} {a.attraction.name}" for a in d.activities) or tr("itin_empty", lang)
            out.append(tr("itin_day", lang, d=d.day_number, items=items))
        return "\n".join(out)

    def _show(self, user, lang: str, state: dict, actions, cards) -> str:
        cur = self._current_itinerary(user, state)
        if cur is None:
            actions.append(ActionOut(type="show", status="failed", detail={"reason": "no_itinerary"}))
            return tr("no_itinerary", lang)
        it = ItineraryService(self.db, llm=self.llm).get(user, cur.id)
        cards.append({"type": "itinerary", "id": str(it.id), "title": it.title})
        actions.append(ActionOut(type="show", status="ok", detail={"itinerary_id": str(it.id)}))
        return tr("itin_header", lang, title=it.title) + "\n" + self._lines(it, lang)

    def _edit(self, user, intent: str, s: nlu.Slots, lang: str, state: dict, actions, cards) -> str:
        cur = self._current_itinerary(user, state)
        if cur is None:
            actions.append(ActionOut(type=intent, status="failed", detail={"reason": "no_itinerary"}))
            return tr("no_itinerary", lang)
        svc = ItineraryService(self.db, llm=self.llm)
        it = svc.get(user, cur.id)
        if intent == "add":
            from app.models.catalog import Attraction

            pool = {
                str(a.id): a.name
                for a in self.db.scalars(
                    select(Attraction).where(
                        Attraction.destination_id == it.destination.id,
                        Attraction.is_published.is_(True),
                        Attraction.deleted_at.is_(None),
                    )
                )
            }
            aid = nlu.match_name(s.activity_text or "", pool)
            if aid is None:
                dest_name = it.destination.name
                actions.append(ActionOut(type="add", status="failed", detail={"reason": "attraction_not_found"}))
                return tr("attraction_not_found", lang, dest=dest_name)
            day = s.day or 1
            if day > it.days:
                return tr("ask_day", lang, n=it.days)
            out = svc.add_activity(user, it.id, AddActivity(attraction_id=uuid.UUID(aid), day_number=day))
            actions.append(
                ActionOut(
                    type="add", status="ok", detail={"itinerary_id": str(out.id), "attraction": pool[aid], "day": day}
                )
            )
            cards.append({"type": "itinerary", "id": str(out.id), "title": out.title})
            return tr("added", lang, name=pool[aid], day=day)
        acts = {str(a.id): a for d in it.day_plans for a in d.activities}
        aid = nlu.match_name(s.activity_text or "", {k: a.attraction.name for k, a in acts.items()})
        if aid is None:
            actions.append(ActionOut(type=intent, status="failed", detail={"reason": "activity_not_found"}))
            return tr(
                "activity_not_found",
                lang,
                names=", ".join(a.attraction.name for a in acts.values()) or tr("itin_empty", lang),
            )
        a = acts[aid]
        if intent == "remove":
            state["pending"] = {
                "type": "confirm",
                "action": "remove_activity",
                "itinerary_id": str(it.id),
                "activity_id": aid,
                "name": a.attraction.name,
            }
            actions.append(
                ActionOut(type="remove", status="awaiting_confirmation", detail={"activity": a.attraction.name})
            )
            return tr("confirm_remove", lang, name=a.attraction.name, day=a.day_number)
        if not s.day:
            return tr("ask_day", lang, n=it.days)
        if s.day > it.days:
            return tr("ask_day", lang, n=it.days)
        state["pending"] = {
            "type": "confirm",
            "action": "move_activity",
            "itinerary_id": str(it.id),
            "activity_id": aid,
            "name": a.attraction.name,
            "day": s.day,
        }
        actions.append(
            ActionOut(type="move", status="awaiting_confirmation", detail={"activity": a.attraction.name, "day": s.day})
        )
        return tr("confirm_move", lang, name=a.attraction.name, day=s.day)

    def _execute_confirmed(self, user, pending: dict, lang: str, actions, cards) -> str:
        svc = ItineraryService(self.db, llm=self.llm)
        iid, aid = uuid.UUID(pending["itinerary_id"]), uuid.UUID(pending["activity_id"])
        if pending["action"] == "remove_activity":
            out = svc.remove_activity(user, iid, aid)
            actions.append(
                ActionOut(type="remove", status="ok", detail={"activity": pending["name"], "itinerary_id": str(out.id)})
            )
            cards.append({"type": "itinerary", "id": str(out.id), "title": out.title})
            return tr("removed", lang, name=pending["name"])
        it = svc.get(user, iid)
        days = {d.day_number: [str(a.id) for a in d.activities] for d in it.day_plans}
        for ids in days.values():
            if str(aid) in ids:
                ids.remove(str(aid))
        days[pending["day"]].append(str(aid))
        out = svc.reorder(
            user,
            iid,
            ReorderRequest(
                days=[{"day_number": d, "activity_ids": [uuid.UUID(x) for x in ids]} for d, ids in days.items()]
            ),
        )
        actions.append(
            ActionOut(
                type="move",
                status="ok",
                detail={"activity": pending["name"], "day": pending["day"], "itinerary_id": str(out.id)},
            )
        )
        cards.append({"type": "itinerary", "id": str(out.id), "title": out.title})
        return tr("moved", lang, name=pending["name"], day=pending["day"])

    def _bookings(self, user, lang: str, actions, cards) -> str:
        items, total = BookingService(self.db).list(user, None, 1, 5)
        if not items:
            actions.append(ActionOut(type="bookings", status="ok", detail={"count": 0}))
            return tr("bookings_none", lang)
        lines = [tr("bookings_header", lang)]
        for b in items:
            status = STATUS_HI.get(b.status, b.status) if lang == "hi" else b.status.replace("_", " ")
            lines.append(
                tr(
                    "booking_line",
                    lang,
                    ref=b.reference,
                    hotel=b.hotel_name,
                    ci=b.check_in.isoformat(),
                    co=b.check_out.isoformat(),
                    status=status,
                )
            )
            cards.append({"type": "booking", "id": str(b.id), "reference": b.reference, "status": b.status})
        actions.append(ActionOut(type="bookings", status="ok", detail={"count": total}))
        return "\n".join(lines)

    def _hotels(self, user, slug: str | None, lang: str, dests: dict[str, str], actions, cards) -> str:
        if not slug:
            actions.append(ActionOut(type="hotels", status="needs_info", detail={"missing": "destination"}))
            return tr("ask_destination", lang, names=", ".join(sorted(dests.values())))
        items, _ = BookingService(self.db).list_hotels(
            published_only=True,
            q=None,
            destination=slug,
            min_stars=None,
            max_price_minor=None,
            sort="stars",
            page=1,
            page_size=3,
        )
        name = dests.get(slug, slug)
        if not items:
            return tr("hotels_none", lang, dest=name)
        lines = [tr("hotels_header", lang, dest=name)]
        for h in items:
            lines.append(
                tr(
                    "hotel_line",
                    lang,
                    name=h.name,
                    stars=h.star_rating or "-",
                    price=f"{(h.from_price_minor or 0) / 100:,.0f}",
                )
            )
            cards.append({"type": "hotel", "slug": h.slug, "name": h.name})
        actions.append(ActionOut(type="hotels", status="ok", detail={"destination": slug}))
        return "\n".join(lines)
