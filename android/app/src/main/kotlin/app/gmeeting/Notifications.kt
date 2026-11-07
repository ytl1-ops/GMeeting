package app.gmeeting

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

object Notifications {
    const val CH_RECORDING = "recording"
    const val CH_STATUS = "status"
    const val ID_RECORDING = 1001
    const val ID_AUTH = 1002

    fun createChannels(ctx: Context) {
        val nm = ctx.getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CH_RECORDING, ctx.getString(R.string.notif_channel_recording), NotificationManager.IMPORTANCE_LOW)
            .apply { setShowBadge(false) })
        nm.createNotificationChannel(NotificationChannel(CH_STATUS, ctx.getString(R.string.notif_channel_status), NotificationManager.IMPORTANCE_DEFAULT))
    }

    private fun open(ctx: Context) = PendingIntent.getActivity(
        ctx, 0, Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    private fun action(ctx: Context, act: String, label: Int, req: Int) = NotificationCompat.Action.Builder(
        0, ctx.getString(label),
        PendingIntent.getService(ctx, req, Intent(ctx, RecordingService::class.java).setAction(act), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT),
    ).build()

    /** Notification permanente de l'enregistrement : obligatoire pour un service micro au premier plan, et rassurante pour l'utilisateur. */
    fun recording(ctx: Context, state: String, startedAtWall: Long): Notification {
        val text = when (state) {
            "paused" -> ctx.getString(R.string.notif_recording_paused)
            "interrupted" -> ctx.getString(R.string.notif_recording_interrupted)
            else -> null
        }
        val b = NotificationCompat.Builder(ctx, CH_RECORDING)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(ctx.getString(R.string.notif_recording_title))
            .setContentIntent(open(ctx))
            .setOngoing(true).setOnlyAlertOnce(true).setSilent(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
        if (text != null) b.setContentText(text)
        if (state == "recording" || state == "interrupted") b.setUsesChronometer(true).setWhen(startedAtWall)
        if (state == "paused") b.addAction(action(ctx, RecordingService.ACTION_RESUME, R.string.notif_action_resume, 1))
        else b.addAction(action(ctx, RecordingService.ACTION_PAUSE, R.string.notif_action_pause, 2))
        b.addAction(action(ctx, RecordingService.ACTION_STOP, R.string.notif_action_stop, 3))
        return b.build()
    }

    fun authNeeded(ctx: Context) {
        if (!NotificationManagerCompat.from(ctx).areNotificationsEnabled()) return
        val n = NotificationCompat.Builder(ctx, CH_STATUS).setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(ctx.getString(R.string.notif_auth_title)).setContentText(ctx.getString(R.string.notif_auth_text))
            .setContentIntent(PendingIntent.getActivity(ctx, 1, Intent(ctx, SetupActivity::class.java), PendingIntent.FLAG_IMMUTABLE))
            .setAutoCancel(true).build()
        @Suppress("MissingPermission") NotificationManagerCompat.from(ctx).notify(ID_AUTH, n)
    }
}
