package com.ridenova.driver.location

import android.app.KeyguardManager
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.graphics.Outline
import android.view.ViewOutlineProvider
import android.provider.Settings
import android.view.Gravity
import android.view.MotionEvent
import android.view.WindowManager
import android.widget.ImageView
import com.ridenova.driver.MainActivity
import com.ridenova.driver.R
import kotlin.math.abs

/** Optional shortcut. Never intercepts touches outside its own small window. */
class DriverOverlay(private val context: Context) {
    private val windows = context.getSystemService(WindowManager::class.java)
    private var bubble: ImageView? = null
    private var params: WindowManager.LayoutParams? = null
    private fun dp(value: Int) = (value * context.resources.displayMetrics.density).toInt()
    fun update(hasOffer: Boolean) {
        val enabled = context.getSharedPreferences("driver_display", Context.MODE_PRIVATE).getBoolean("floating_shortcut", false)
        if (!enabled || !Settings.canDrawOverlays(context) || DriverVisibility.foreground ||
            context.getSystemService(KeyguardManager::class.java).isKeyguardLocked) { hide(); return }
        if (bubble == null) {
            val view = ImageView(context).apply {
                setImageResource(R.drawable.ic_ridenova_driver)
                background = android.graphics.drawable.GradientDrawable().apply {
                    shape = android.graphics.drawable.GradientDrawable.OVAL
                    setColor(android.graphics.Color.BLACK)
                }
                outlineProvider = object : ViewOutlineProvider() {
                    override fun getOutline(view: android.view.View, outline: Outline) {
                        outline.setOval(0, 0, view.width, view.height)
                    }
                }
                scaleType = ImageView.ScaleType.CENTER_CROP
                clipToOutline = true
                elevation = dp(8).toFloat()
                contentDescription = "Open RideNova Driver. Drag to move."
                setOnClickListener {
                    runCatching { context.startActivity(Intent(context, MainActivity::class.java)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP)) }
                }
            }
            val layout = WindowManager.LayoutParams(dp(60), dp(60), WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                PixelFormat.TRANSLUCENT).apply { gravity = Gravity.TOP or Gravity.LEFT; x = dp(12); y = dp(200) }
            var downX = 0f; var downY = 0f; var originalX = 0; var originalY = 0
            view.setOnTouchListener { _, event ->
                when (event.actionMasked) {
                    MotionEvent.ACTION_DOWN -> { downX = event.rawX; downY = event.rawY; originalX = layout.x; originalY = layout.y; true }
                    MotionEvent.ACTION_MOVE -> {
                        val screen = context.resources.displayMetrics
                        layout.x = (originalX + (event.rawX-downX).toInt()).coerceIn(0, (screen.widthPixels-dp(60)).coerceAtLeast(0))
                        layout.y = (originalY + (event.rawY-downY).toInt()).coerceIn(0, (screen.heightPixels-dp(90)).coerceAtLeast(0))
                        runCatching { windows.updateViewLayout(view, layout) }; true
                    }
                    MotionEvent.ACTION_UP -> { if (abs(event.rawX-downX)<dp(8) && abs(event.rawY-downY)<dp(8)) view.performClick(); true }
                    else -> false
                }
            }
            runCatching { windows.addView(view, layout) }.onSuccess { bubble = view; params = layout }
        }
        bubble?.alpha = if (hasOffer) 1f else .94f
        bubble?.contentDescription = if (hasOffer) "New ride request. Tap to review in RideNova." else "Open RideNova Driver. Drag to move."
    }
    fun hide() { bubble?.let { runCatching { windows.removeView(it) } }; bubble = null; params = null }
}
