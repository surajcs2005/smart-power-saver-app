import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import Device, PowerLog
from django.db.models import Avg, Sum
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from datetime import timedelta
from collections import defaultdict
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.conf import settings
import urllib.request
import urllib.error
from .forms import SignupForm

@login_required
def dashboard(request):
    return render(request, 'powerapp/dashboard.html')

@login_required
def analytics(request):
    return render(request, 'powerapp/analytics.html')

@login_required
def settings(request):
    return render(request, 'powerapp/settings.html')

@login_required
def api_devices(request):
    devices = Device.objects.all()
    data = []
    for d in devices:
        logs = list(d.logs.order_by('-timestamp')[:10].values('timestamp', 'power_watts'))
        logs.reverse()
        data.append({
            'id': d.id,
            'name': d.name,
            'room': d.room,
            'is_on': d.is_on,
            'last_seen': d.last_seen.isoformat() if d.last_seen else None,
            'recent_logs': logs
        })
    return JsonResponse({'devices': data})

@csrf_exempt
@login_required
def api_toggle_device(request, device_id):
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid method")
    d = get_object_or_404(Device, id=device_id)
    d.is_on = not d.is_on
    d.last_seen = timezone.now()
    d.save()
    return JsonResponse({'id': d.id, 'is_on': d.is_on})

@csrf_exempt
@login_required
def api_post_reading(request):
    try:
        data = json.loads(request.body.decode())
        device_id = data.get('device_id')
        power = float(data.get('power_watts'))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")
    d = get_object_or_404(Device, id=device_id)
    PowerLog.objects.create(device=d, power_watts=power)
    d.is_on = power > 1
    d.last_seen = timezone.now()
    d.save()
    return JsonResponse({'status': 'ok'})

@login_required
def api_device_logs(request, device_id):
    d = get_object_or_404(Device, id=device_id)
    logs = list(d.logs.order_by('-timestamp')[:100].values('timestamp', 'power_watts'))
    return JsonResponse({'device': d.name, 'logs': logs})

def _float(val, default):
    try:
        return float(val)
    except Exception:
        return default

def _filter_logs(qs, request):
    room = request.GET.get('room')
    if room:
        qs = qs.filter(device__room__iexact=room)
    device_ids = request.GET.getlist('device')
    if device_ids:
        qs = qs.filter(device_id__in=device_ids)
    return qs

def _series_from_queryset(qs, date_field, value_field='power_watts__avg'):
    return [
        {
            'date': item[date_field],
            'value': round(item[value_field] or 0, 2),
        }
        for item in qs
    ]

def _top_devices(qs, limit=5):
    agg = (
        qs.values('device__id', 'device__name')
        .annotate(avg_power=Avg('power_watts'))
        .order_by('-avg_power')[:limit]
    )
    return [
        {
            'id': r['device__id'],
            'name': r['device__name'],
            'avg_power': round(r['avg_power'] or 0, 2),
        }
        for r in agg
    ]

@login_required
def api_usage_summary(request):
    now = timezone.now()
    # default last 30 days
    default_start = now - timedelta(days=30)
    start = request.GET.get('start')
    end = request.GET.get('end')
    try:
        start_dt = timezone.datetime.fromisoformat(start) if start else default_start
        end_dt = timezone.datetime.fromisoformat(end) if end else now
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt, timezone.get_current_timezone())
        if timezone.is_naive(end_dt):
            end_dt = timezone.make_aware(end_dt, timezone.get_current_timezone())
    except Exception:
        start_dt, end_dt = default_start, now

    logs = PowerLog.objects.filter(timestamp__range=(start_dt, end_dt))
    logs = _filter_logs(logs, request)

    # Daily (last 30 days)
    daily_qs = (
        logs.annotate(day=TruncDay('timestamp'))
        .values('day')
        .annotate(Avg('power_watts'))
        .order_by('day')
    )
    daily = _series_from_queryset(daily_qs, 'day')

    # Weekly (last 12 weeks)
    week_start = now - timedelta(weeks=12)
    weekly_logs = logs.filter(timestamp__gte=week_start)
    weekly_qs = (
        weekly_logs.annotate(week=TruncWeek('timestamp'))
        .values('week')
        .annotate(Avg('power_watts'))
        .order_by('week')
    )
    weekly = _series_from_queryset(weekly_qs, 'week')

    # Monthly (last 12 months)
    month_start = now - timedelta(days=365)
    monthly_logs = logs.filter(timestamp__gte=month_start)
    monthly_qs = (
        monthly_logs.annotate(month=TruncMonth('timestamp'))
        .values('month')
        .annotate(Avg('power_watts'))
        .order_by('month')
    )
    monthly = _series_from_queryset(monthly_qs, 'month')

    top = _top_devices(logs, limit=5)

    return JsonResponse({
        'daily': daily,
        'weekly': weekly,
        'monthly': monthly,
        'top_devices': top,
        'units': 'W (average)'
    })

@login_required
def api_compare_summary(request):
    now = timezone.now()
    start = request.GET.get('start')
    end = request.GET.get('end')
    try:
        start_dt = timezone.datetime.fromisoformat(start) if start else now - timedelta(days=30)
        end_dt = timezone.datetime.fromisoformat(end) if end else now
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt, timezone.get_current_timezone())
        if timezone.is_naive(end_dt):
            end_dt = timezone.make_aware(end_dt, timezone.get_current_timezone())
    except Exception:
        start_dt, end_dt = now - timedelta(days=30), now

    logs = PowerLog.objects.filter(timestamp__range=(start_dt, end_dt))
    logs = _filter_logs(logs, request)

    # Average power per device
    by_device_qs = (
        logs.values('device__id', 'device__name', 'device__room')
        .annotate(avg_power=Avg('power_watts'))
        .order_by('-avg_power')
    )
    by_device = [
        {
            'id': r['device__id'],
            'name': r['device__name'],
            'room': r['device__room'] or '',
            'avg_power': round(r['avg_power'] or 0, 2),
        }
        for r in by_device_qs
    ]

    # Average power by room
    by_room_qs = (
        logs.values('device__room')
        .annotate(avg_power=Avg('power_watts'))
        .order_by('-avg_power')
    )
    by_room = [
        {
            'room': r['device__room'] or 'Unassigned',
            'avg_power': round(r['avg_power'] or 0, 2),
        }
        for r in by_room_qs
    ]

    # Ranking top 10 devices
    ranking = by_device[:10]

    return JsonResponse({
        'by_device': by_device,
        'by_room': by_room,
        'ranking': ranking,
        'units': 'W (average)'
    })

@login_required
def compare(request):
    return render(request, 'powerapp/compare.html')

# Pages
@login_required
def control(request):
    return render(request, 'powerapp/control.html')

@login_required
def rules(request):
    return render(request, 'powerapp/rules.html')

@login_required
def notifications_page(request):
    return render(request, 'powerapp/notifications.html')

@login_required
def history(request):
    return render(request, 'powerapp/history.html')

@login_required
def suggestions(request):
    return render(request, 'powerapp/suggestions.html')

@login_required
def management(request):
    return render(request, 'powerapp/management.html')

# Analytics/aux APIs
@login_required
def api_heatmap(request):
    now = timezone.now()
    start = request.GET.get('start')
    end = request.GET.get('end')
    try:
        start_dt = timezone.datetime.fromisoformat(start) if start else now - timedelta(days=7)
        end_dt = timezone.datetime.fromisoformat(end) if end else now
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt, timezone.get_current_timezone())
        if timezone.is_naive(end_dt):
            end_dt = timezone.make_aware(end_dt, timezone.get_current_timezone())
    except Exception:
        start_dt, end_dt = now - timedelta(days=7), now

    logs = PowerLog.objects.filter(timestamp__range=(start_dt, end_dt))
    logs = _filter_logs(logs, request)

    # Aggregate by day and hour
    buckets = defaultdict(list)
    for row in logs.values('timestamp', 'power_watts'):
        ts = row['timestamp']
        key = (ts.date().isoformat(), ts.hour)
        buckets[key].append(row['power_watts'])

    series = []
    for (d, h), vals in sorted(buckets.items()):
        series.append({'date': d, 'hour': h, 'value': round(sum(vals)/max(len(vals),1), 2)})
    return JsonResponse({'heatmap': series, 'units': 'W (avg)'})

@login_required
def api_notifications(request):
    threshold = _float(request.GET.get('threshold') or 250.0, 250.0)
    since_hours = int(request.GET.get('since') or 24)
    since = timezone.now() - timedelta(hours=since_hours)
    logs = PowerLog.objects.filter(timestamp__gte=since, power_watts__gte=threshold).select_related('device')
    alerts = []
    for log in logs.order_by('-timestamp')[:100]:
        alerts.append({
            'device_id': log.device_id,
            'device': log.device.name,
            'room': log.device.room,
            'power_watts': log.power_watts,
            'timestamp': log.timestamp,
            'action': 'Consider turning off or reducing usage'
        })
    return JsonResponse({'alerts': alerts})

@login_required
def api_suggestions(request):
    # Simple heuristics: devices with high avg -> suggest schedule/auto-off
    now = timezone.now()
    start_dt = now - timedelta(days=7)
    logs = PowerLog.objects.filter(timestamp__gte=start_dt)
    agg = (
        logs.values('device__id', 'device__name', 'device__room')
        .annotate(avg_power=Avg('power_watts'))
        .order_by('-avg_power')[:10]
    )
    suggestions = []
    for r in agg:
        avgw = r['avg_power'] or 0
        if avgw < 10:
            continue
        suggestions.append({
            'device_id': r['device__id'],
            'device': r['device__name'],
            'room': r['device__room'] or '',
            'avg_power': round(avgw, 1),
            'suggestion': 'Schedule auto-shutdown during off-hours',
            'expected_savings_rs': round((avgw * 6.0 * 8 * 30) / 1000, 2)
        })
    return JsonResponse({'suggestions': suggestions})

def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect('dashboard')
    else:
        form = SignupForm()
    return render(request, 'powerapp/signup.html', {'form': form})

def logout_view(request):
    """Log the user out on any method and redirect to login page."""
    try:
        auth_logout(request)
    finally:
        return redirect('login')

@login_required
def api_chat(request):
    try:
        data = json.loads(request.body.decode()) if request.body else {}
    except Exception:
        data = {}
    prompt = (data.get('message') or '').strip()

    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    # If no key is set, fallback to local heuristic
    if not api_key:
        if not prompt:
            reply = "Hi! Ask me about power usage, devices, or automation."
        else:
            p = prompt.lower()
            if 'save' in p or 'reduce' in p:
                reply = "Try scheduling high-consumption devices off at night and enable auto-shutdown on idle."
            elif 'peak' in p:
                reply = "Peak usage is typically early evening. Consider delaying washing machine or heater cycles."
            elif 'cost' in p or 'bill' in p:
                reply = "Based on current averages, lowering AC by 1°C can save ~5-10% monthly."
            elif 'device' in p or 'which' in p:
                reply = "Top consumers this week are TVs, ACs, and computers. Check the Compare page for details."
            else:
                reply = "I can help with devices, schedules, and savings tips. Ask me about top-consuming devices or how to cut costs."
        return JsonResponse({'reply': reply, 'source': 'local'})

    # If key exists, attempt calling OpenAI Chat Completions API (HTTP)
    try:
        body = json.dumps({
            "model": "gpt-4o-mini",
            "messages": [
                {"role":"system","content":"You are Smart Power Saver AI assistant. Be concise, friendly, and practical. Focus on energy tips, device control, and schedules."},
                {"role":"user","content": prompt or "Hello"}
            ],
            "temperature": 0.4
        }).encode('utf-8')
        req = urllib.request.Request(
            url='https://api.openai.com/v1/chat/completions',
            data=body,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode())
            reply = payload.get('choices', [{}])[0].get('message', {}).get('content', '').strip() or 'Sorry, I could not generate a reply.'
        return JsonResponse({'reply': reply, 'source': 'openai'})
    except Exception:
        # Fallback on network/API error
        return JsonResponse({'reply': 'Network issue contacting AI service. Try again later.', 'source': 'error'})
