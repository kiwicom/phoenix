from datetime import datetime

import arrow
from django.http import Http404, HttpResponseForbidden, HttpResponseBadRequest
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from django.shortcuts import redirect
from rest_framework.decorators import api_view

from ..core.models import Monitor, Outage, Solution
from ..core.utils import user_can_modify_outage
from ..slackbot.utils import resolved_at_to_utc
from .forms import MonitorUpdate, OutageCreateForm, OutageUpdateForm, SolutionCreateForm


class OutagesList(ListView):
    model = Outage
    template_name = "outages/outages_list.html"
    paginate_by = 20

    def get_context_data(self, **kwargs):  # pylint: disable=arguments-differ
        context = super().get_context_data(**kwargs)
        context["user_id"] = self.request.user.id
        return context


class OutageCreate(CreateView):
    form_class = OutageCreateForm
    model = Outage
    template_name = "outages/outage_form.html"

    def get_success_url(self):
        return reverse("outage_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_form(self, form_class=None):
        """Return an instance of the form to be used in this view."""
        if form_class is None:
            form_class = self.get_form_class()
        # Create resolved_at field from datepicker and timepicker values.
        kwargs = self.get_form_kwargs()
        if kwargs.get("data") and not kwargs["data"]["eta"]:
            # If saving new data into form.
            kwargs["data"] = kwargs["data"].copy()  # Change QueryDict to mutable.
            kwargs["data"]["eta"] = 0
        return form_class(**kwargs)


class OutageDetail(DetailView):
    model = Outage
    template_name = "outages/outage_detail.html"

    def get_context_data(self, **kwargs):  # pylint: disable=arguments-differ
        context = super().get_context_data(**kwargs)
        context["user_can_modify"] = user_can_modify_outage(
            self.request.user.id, self.kwargs["pk"], True
        )
        return context


class OutageUpdate(UpdateView):
    form_class = OutageUpdateForm
    model = Outage
    template_name = "outages/outage_form.html"
    http_method_names = ["get", "post"]

    def get_initial(self):
        initial = super().get_initial()
        initial["communication_assignee"] = self.object.communication_assignee
        initial["solution_assignee"] = self.object.solution_assignee
        initial["eta"] = self.object.eta
        return initial

    def get_success_url(self):
        return reverse("outage_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        form.modified_by = self.request.user
        form.eta_last_modified = timezone.now()
        return super().form_valid(form)

    def get(self, request, *args, **kwargs):
        if not user_can_modify_outage(self.request.user.id, self.kwargs["pk"]):
            return HttpResponseForbidden()
        return super().get(request, args, kwargs)

    def post(self, request, *args, **kwargs):
        if not user_can_modify_outage(self.request.user.id, self.kwargs["pk"]):
            return HttpResponseForbidden()
        return super().post(request, args, kwargs)


class SolutionAbstract(CreateView):
    class Meta:
        abstract = True

    form_class = SolutionCreateForm
    model = Solution
    template_name = "outages/resolution_form.html"
    http_method_names = ["get", "post"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["outage"] = Outage.objects.get(pk=self.kwargs["pk"])
        context["time_start_from"] = datetime.now().strftime("%I:%M %p")
        return context

    def get_success_url(self):
        return reverse("outage_detail", kwargs={"pk": self.kwargs["pk"]})

    def form_valid(self, form):
        outage_id = self.kwargs["pk"]
        form.modified_by = self.request.user
        form.instance.outage_id = outage_id
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_form(self, form_class=None):
        """Return an instance of the form to be used in this view."""
        if form_class is None:
            form_class = self.get_form_class()
        # Create resolved_at field from datepicker and timepicker values.
        kwargs = self.get_form_kwargs()
        if kwargs.get("data"):
            # If saving new data into form.
            kwargs["data"] = kwargs["data"].copy()  # Change QueryDict to mutable.
            date = kwargs["data"]["datepicker"]
            time = kwargs["data"]["timepicker"]
            resolved_at = arrow.get(f"{date} {time}", "MMM DD, YYYY hh:mm A")
            user_tz = kwargs["data"]["timezone"]
            update_values = {"resolved_at": resolved_at_to_utc(resolved_at, user_tz)}
            report_url = kwargs["data"]["report_url"]
            if report_url:
                if not report_url.startswith("http"):
                    report_url = f"https://{report_url}"
                update_values["report_url"] = report_url
            kwargs["data"].update(update_values)
        return form_class(**kwargs)


class SolutionCreate(SolutionAbstract, CreateView):
    def get(self, request, *args, **kwargs):
        if not user_can_modify_outage(self.request.user.id, self.kwargs["pk"]):
            return HttpResponseForbidden()
        return super().get(request, args, kwargs)

    def post(self, request, *args, **kwargs):
        if not user_can_modify_outage(self.request.user.id, self.kwargs["pk"]):
            return HttpResponseForbidden()
        return super().post(request, args, kwargs)


class SolutionUpdate(SolutionAbstract, UpdateView):
    def get_object(self, queryset=None):
        outage = Outage.objects.get(pk=self.kwargs["pk"])
        try:
            solution = outage.solution
        except Solution.DoesNotExist:
            raise Http404("solution not found")
        return solution

    def get(self, request, *args, **kwargs):
        if not user_can_modify_outage(
            self.request.user.id, self.kwargs["pk"], allow_resolved=True
        ):
            return HttpResponseForbidden()
        return super().get(request, args, kwargs)

    def post(self, request, *args, **kwargs):
        if not user_can_modify_outage(
            self.request.user.id, self.kwargs["pk"], allow_resolved=True
        ):
            return HttpResponseForbidden()
        return super().post(request, args, kwargs)


@api_view(["GET"])
def reopen_outage(request, pk):
    try:
        outage = Outage.objects.get(id=pk)
    except Outage.DoesNotExist:
        raise Http404("Outage doesn't exist.")
    if outage.is_resolved:
        outage.resolved = False
        outage.save(modified_by=request.user)
    else:
        return HttpResponseBadRequest("Can't reopen unresolved outage.")
    return redirect("outage_detail", pk=pk)


class MonitorList(ListView):
    model = Monitor
    template_name = "outages/monitors/list.html"


class MonitorDetail(DetailView):
    model = Monitor
    template_name = "outages/monitors/detail.html"


class MonitorUpdateView(UpdateView):
    model = Monitor
    form_class = MonitorUpdate
    template_name = "outages/monitors/form.html"

    def form_valid(self, form):
        form.modified_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("monitor_detail", kwargs={"pk": self.object.pk})
