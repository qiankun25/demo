<template>
  <div class="daily-subscription">
    <keep-alive>
      <router-view />
    </keep-alive>
  </div>
</template>

<script setup>
defineOptions({
  name: 'DailySubscription'
})
</script>

<style scoped>
.daily-subscription {
  max-width: 1200px;
  margin: 0 auto;
}
</style>
