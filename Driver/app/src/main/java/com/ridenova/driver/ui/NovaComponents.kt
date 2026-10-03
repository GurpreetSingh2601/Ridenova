package com.ridenova.driver.ui
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import com.ridenova.driver.R
@Composable
internal fun NovaBrand(size: Int = 48) {
    Image(painterResource(R.drawable.ic_ridenova_driver),"RideNova Driver",Modifier.size(size.dp).clip(RoundedCornerShape((size*.25f).dp)))
}
@Composable
internal fun NovaSection(title: String, subtitle: String? = null) {
    Column(verticalArrangement=Arrangement.spacedBy(4.dp)) {
        Text(title,style=MaterialTheme.typography.titleLarge,modifier=Modifier.semantics { heading() })
        subtitle?.let { Text(it,style=MaterialTheme.typography.bodyMedium,color=MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}
@Composable
internal fun NovaNotice(title: String,message: String,error: Boolean = false) {
    Surface(Modifier.fillMaxWidth().semantics { liveRegion=LiveRegionMode.Polite },shape=RoundedCornerShape(16.dp),
        color=if(error) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.surfaceVariant,
        contentColor=if(error) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onSurfaceVariant) {
        Row(Modifier.padding(16.dp),horizontalArrangement=Arrangement.spacedBy(12.dp)) {
            Icon(if(error) Icons.Default.ErrorOutline else Icons.Default.Info,null,Modifier.size(20.dp))
            Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(4.dp)) {
                Text(title,style=MaterialTheme.typography.titleSmall);Text(message,style=MaterialTheme.typography.bodySmall)
            }
        }
    }
}
